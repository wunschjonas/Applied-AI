from __future__ import annotations

from typing import Any

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
            decision="Image prompt generation requested.",
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
            decision="HuggingFace returned an image prompt draft.",
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
    ) -> dict[str, Any]:
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
        model_id = getattr(self.hf, "hf_image_model_id", None) or "unconfigured"

        try:
            self.trace(
                trace,
                decision="Image prompt is ready for text-to-image inference.",
                action="call_text_to_image_model",
                observation=f"Calling HuggingFace text-to-image model {model_id}.",
            )
            image_bytes = self.hf.generate_image(prompt=prompt, negative_prompt=negative_prompt)

            self.trace(
                trace,
                decision="HuggingFace returned image bytes.",
                action="store_generated_image",
                observation="Storing generated image bytes as a local PNG file.",
            )
            stored = self.image_storage.save_png(image_bytes, filename_stem=post_id)
            artifact.update(stored)

            self.trace(
                trace,
                decision="Generated image file is available.",
                action="return_image_artifact",
                observation=f"Stored {stored['image_filename']} at {stored['image_url']}.",
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
                decision="Image prompt exists but image generation failed.",
                action="return_image_artifact",
                observation=error,
                status_value="partial_success",
            )
            return artifact

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
        permanent_terms = ("hf_token", "permission", "forbidden", "unauthorized", "unsupported", "not found", "invalid configuration")
        return any(term in lowered for term in transient_terms) and not any(term in lowered for term in permanent_terms)
