from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image

from app.agents.base_agent import BaseAgent
from app.services.image_storage_service import ImageStorageService


class ImageAgent(BaseAgent):
    name = "ImageAgent"

    def __init__(self, *args, image_storage: ImageStorageService | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.image_storage = image_storage or ImageStorageService()

    def generate_prompt(
        self,
        task: str,
        trace: dict,
        platform: str | None = None,
        visual_style: str | None = None,
        context: str | dict[str, Any] | None = None,
        rag_context: str | None = None,
    ) -> dict[str, Any]:
        self.trace(
            trace,
            thought="Image prompt generation requested.",
            action="generate_image_prompt",
            observation=f"Platform={platform or 'unspecified'}, style={visual_style or 'model choice'}.",
        )

        prompt_text = self.hf.generate(
            system_prompt=(
                "You write production-ready image generation prompts for marketing visuals. "
                "Return a strong prompt, a short negative prompt, and a suggested style."
            ),
            user_prompt=self._build_prompt(task, platform, visual_style, context, rag_context),
            max_tokens=500,
        )

        result = {
            "image_prompt": prompt_text,
            "negative_prompt_optional": "low quality, distorted text, blurry, off-brand, cluttered",
            "suggested_style": visual_style or "clean commercial marketing visual",
        }

        self.trace(
            trace,
            thought="HuggingFace returned an image prompt draft.",
            action="return_image_prompt_artifact",
            observation=f"Generated prompt with {len(prompt_text)} characters.",
        )

        return result

    def generate_image(
        self,
        task: str,
        trace: dict,
        platform: str | None = None,
        visual_style: str | None = None,
        context: str | dict[str, Any] | None = None,
        rag_context: str | None = None,
        validation_feedback: str | None = None,
        post_id: str | None = None,
        source_image: bytes | None = None,
        current_image: bytes | None = None,
        strength: float = 0.7,
    ) -> dict[str, Any]:
        """Generate a new image from text and optional visual inputs.

        - ``source_image``: user reference upload
        - ``current_image``: existing post preview image on disk
        When both are present, they are composed into one img2img input.
        """
        if current_image is None and post_id:
            current_image = self.image_storage.read_post_image(post_id)

        prompt_task = task
        if validation_feedback:
            prompt_task = f"{task}\n\nValidation feedback for retry: {validation_feedback}"

        artifact = self.generate_prompt(
            task=prompt_task,
            trace=trace,
            platform=platform,
            visual_style=visual_style,
            context=context,
            rag_context=rag_context,
        )

        prompt = artifact.get("image_prompt", "")
        negative_prompt = artifact.get("negative_prompt_optional")
        img2img_bytes, img2img_source = self._resolve_img2img_source(current_image, source_image)
        use_img2img = bool(img2img_bytes)
        model_id = (
            getattr(self.hf, "hf_image_to_image_model_id", None)
            if use_img2img
            else getattr(self.hf, "hf_image_model_id", None)
        ) or "unconfigured"

        try:
            generation_mode = "text_to_image"
            if use_img2img:
                self.trace(
                    trace,
                    thought="Visual inputs ready for image-to-image inference.",
                    action="call_image_to_image_model",
                    observation=(
                        f"Calling HuggingFace image-to-image model {model_id} "
                        f"with strength={strength}; source={img2img_source}."
                    ),
                )
                try:
                    image_bytes = self.hf.generate_image_from_image(
                        prompt=prompt,
                        image_bytes=img2img_bytes or b"",
                        negative_prompt=negative_prompt,
                        strength=strength,
                    )
                    generation_mode = "image_to_image"
                except Exception as img2img_exc:
                    self.trace(
                        trace,
                        thought="Image-to-image failed; falling back to text-to-image.",
                        action="fallback_text_to_image",
                        observation=f"{type(img2img_exc).__name__}: {img2img_exc}",
                        status_value="warning",
                    )
                    txt_model = getattr(self.hf, "hf_image_model_id", None) or "unconfigured"
                    self.trace(
                        trace,
                        thought="Generating a new image from the enriched prompt.",
                        action="call_text_to_image_model",
                        observation=f"Calling HuggingFace text-to-image model {txt_model}.",
                    )
                    image_bytes = self.hf.generate_image(prompt=prompt, negative_prompt=negative_prompt)
                    generation_mode = "text_to_image_fallback"
                    artifact["image_to_image_error"] = f"{type(img2img_exc).__name__}: {img2img_exc}"
            else:
                self.trace(
                    trace,
                    thought="Image prompt is ready for text-to-image inference.",
                    action="call_text_to_image_model",
                    observation=f"Calling HuggingFace text-to-image model {model_id}.",
                )
                image_bytes = self.hf.generate_image(prompt=prompt, negative_prompt=negative_prompt)

            self.trace(
                trace,
                thought="HuggingFace returned image bytes.",
                action="store_generated_image",
                observation="Storing generated image bytes as a local PNG file.",
            )
            stored = self.image_storage.save_png(image_bytes, filename_stem=post_id)
            artifact.update(stored)
            artifact["generation_mode"] = generation_mode
            artifact["img2img_source"] = img2img_source
            artifact["used_current_image"] = bool(current_image)
            artifact["used_reference_image"] = bool(source_image)
            if use_img2img:
                artifact["used_image_to_image"] = generation_mode == "image_to_image"
                artifact["image_to_image_strength"] = strength

            self.trace(
                trace,
                thought="Generated image file is available.",
                action="return_image_artifact",
                observation=(
                    f"Stored {stored['image_filename']} at {stored['image_url']} "
                    f"({generation_mode}, source={img2img_source})."
                ),
            )
            return artifact
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            artifact.update(
                {
                    "image_url": None,
                    "image_filename": None,
                    "image_content_type": None,
                    "image_error": error,
                    "partial_success": True,
                    "retryable": self._is_retryable_error(error),
                }
            )
            self.trace(
                trace,
                thought="Image prompt exists but image generation failed.",
                action="return_image_artifact",
                observation=error,
                status_value="partial_success",
            )
            return artifact

    def _resolve_img2img_source(
        self,
        current_image: bytes | None,
        reference_image: bytes | None,
    ) -> tuple[bytes | None, str]:
        if current_image and reference_image:
            return self._compose_side_by_side(current_image, reference_image), "current_plus_reference"
        if current_image:
            return current_image, "current_post"
        if reference_image:
            return reference_image, "reference"
        return None, "none"

    def _compose_side_by_side(self, left_bytes: bytes, right_bytes: bytes) -> bytes:
        """Pack current post (left) + reference (right) into one img2img input."""
        left = Image.open(BytesIO(left_bytes)).convert("RGB")
        right = Image.open(BytesIO(right_bytes)).convert("RGB")
        target_height = min(max(left.height, right.height, 512), 1024)
        left = self._resize_to_height(left, target_height)
        right = self._resize_to_height(right, target_height)
        canvas = Image.new("RGB", (left.width + right.width, target_height), color=(255, 255, 255))
        canvas.paste(left, (0, 0))
        canvas.paste(right, (left.width, 0))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _resize_to_height(image: Image.Image, height: int) -> Image.Image:
        if image.height == height:
            return image
        width = max(1, int(image.width * (height / image.height)))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    def _build_prompt(
        self,
        task: str,
        platform: str | None,
        visual_style: str | None,
        context: str | dict[str, Any] | None,
        rag_context: str | None = None,
    ) -> str:
        context_text = self._context_to_text(context)
        memory_section = f"\n- Memory context: {rag_context}" if rag_context else ""
        return f"""
Create an image generation prompt for this marketing task:
{task}

Details:
- Platform: {platform or "unspecified"}
- Visual style: {visual_style or "choose an appropriate style"}
- Context: {context_text}{memory_section}

The prompt should describe subject, composition, lighting, colors, mood, and any platform-specific framing.
Do not request readable text inside the image unless explicitly required.
""".strip()

    def _context_to_text(self, context: str | dict[str, Any] | None) -> str:
        if context is None:
            return "none"
        if isinstance(context, str):
            return context
        return ", ".join(f"{key}: {value}" for key, value in context.items()) or "none"

    def _is_retryable_error(self, error: str) -> bool:
        lowered = error.lower()
        transient_terms = ("transient", "timeout", "temporarily", "unavailable", "503", "429", "rate limit")
        permanent_terms = (
            "hf_token",
            "permission",
            "forbidden",
            "unauthorized",
            "unsupported",
            "not found",
            "invalid configuration",
        )
        return any(term in lowered for term in transient_terms) and not any(
            term in lowered for term in permanent_terms
        )
