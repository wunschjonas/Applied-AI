from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from huggingface_hub import InferenceClient
from PIL import Image

# image_to_text is only reliably served by the native HF Inference provider.
# "auto" often routes elsewhere and yields StopIteration / empty responses.
DEFAULT_CAPTION_MODELS = (
    "Salesforce/blip-image-captioning-base",
    "Salesforce/blip-image-captioning-large",
    "nlpconnect/vit-gpt2-image-captioning",
)


class HuggingFaceService:
    def __init__(
        self,
        hf_token: str | None,
        hf_model_id: str,
        hf_image_model_id: str | None = None,
        hf_caption_model_id: str | None = None,
        hf_image_to_image_model_id: str | None = None,
    ):
        if not hf_token:
            raise ValueError("HF_TOKEN is missing. Configure it in backend/.env before calling an agent.")

        self.hf_model_id = hf_model_id
        self.hf_image_model_id = hf_image_model_id
        self.hf_caption_model_id = hf_caption_model_id or DEFAULT_CAPTION_MODELS[0]
        self.hf_image_to_image_model_id = (
            hf_image_to_image_model_id or "stabilityai/stable-diffusion-xl-base-1.0"
        )
        # Default client: chat / text-to-image / img2img (provider auto).
        self.client = InferenceClient(token=hf_token)
        # Captioning must pin hf-inference — image_to_text is not on fal/replicate/etc.
        self.caption_client = InferenceClient(token=hf_token, provider="hf-inference")

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str:
        return self.generate_text(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens)

    def generate_text(self, system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str:
        try:
            response = self.client.chat_completion(
                model=self.hf_model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
        except Exception as exc:
            raise RuntimeError(f"HuggingFace request failed: {type(exc).__name__}: {exc}") from exc

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError("HuggingFace returned an empty response.")

        return content.strip()

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 400,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Run chat_completion with native function-calling tools.

        Returns {"content": str | None, "tool_calls": [{"id", "name", "arguments"}, ...]}.
        """
        try:
            response = self.client.chat_completion(
                model=self.hf_model_id,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise RuntimeError(f"HuggingFace tool request failed: {type(exc).__name__}: {exc}") from exc

        message = response.choices[0].message
        content = message.content
        tool_calls: list[dict[str, Any]] = []
        for index, raw in enumerate(getattr(message, "tool_calls", None) or []):
            function = raw.function
            arguments = function.arguments
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments) if arguments.strip() else {}
                except json.JSONDecodeError:
                    arguments = {"_raw": arguments}
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(
                {
                    "id": getattr(raw, "id", None) or f"call_{index}",
                    "name": function.name,
                    "arguments": arguments,
                }
            )

        return {
            "content": content.strip() if isinstance(content, str) and content.strip() else None,
            "tool_calls": tool_calls,
        }

    def describe_image(self, image_bytes: bytes, model: str | None = None) -> str:
        """Caption an uploaded image for memory storage.

        Uses the ``hf-inference`` provider — ``image_to_text`` is not available on
        most third-party Inference Providers (fal, replicate, …).
        """
        if not image_bytes:
            raise ValueError("Cannot describe an empty image.")

        candidates = [
            model or self.hf_caption_model_id,
            *DEFAULT_CAPTION_MODELS,
        ]
        seen: set[str] = set()
        errors: list[str] = []
        pil_image = self._bytes_to_rgb_image(image_bytes)

        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            for payload, label in (
                (image_bytes, "bytes"),
                (pil_image, "pil"),
            ):
                try:
                    result = self.caption_client.image_to_text(payload, model=candidate)
                except Exception as exc:
                    errors.append(f"{candidate}/{label}: {type(exc).__name__}: {exc}")
                    continue
                text = self._extract_caption_text(result)
                if text:
                    return text
                errors.append(f"{candidate}/{label}: empty caption")

        raise RuntimeError(
            "HuggingFace image caption failed for all models. " + " | ".join(errors[:4])
        )

    @staticmethod
    def _extract_caption_text(result: Any) -> str | None:
        if isinstance(result, str) and result.strip():
            return result.strip()
        generated = getattr(result, "generated_text", None)
        if isinstance(generated, str) and generated.strip():
            return generated.strip()
        if isinstance(result, dict):
            text = str(result.get("generated_text") or "").strip()
            if text:
                return text
        text = str(result).strip()
        if text and text not in {"None", "{}"}:
            return text
        return None

    def _bytes_to_rgb_image(self, image_bytes: bytes) -> Image.Image:
        try:
            return Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise ValueError(f"Source image could not be decoded: {type(exc).__name__}: {exc}") from exc

    def generate_image(self, prompt: str, negative_prompt: str | None = None) -> bytes:
        if not self.hf_image_model_id:
            raise ValueError("HF_IMAGE_MODEL_ID is missing. Configure it in backend/.env before generating images.")

        try:
            kwargs: dict[str, Any] = {"model": self.hf_image_model_id}
            if negative_prompt:
                kwargs["negative_prompt"] = negative_prompt
            image = self.client.text_to_image(prompt, **kwargs)
        except Exception as exc:
            raise self._image_error(exc, mode="text-to-image") from exc

        return self._image_response_to_png_bytes(image)

    def generate_image_from_image(
        self,
        prompt: str,
        image_bytes: bytes,
        *,
        negative_prompt: str | None = None,
        strength: float = 0.7,
    ) -> bytes:
        if not self.hf_image_to_image_model_id:
            raise ValueError(
                "HF_IMAGE_TO_IMAGE_MODEL_ID is missing. "
                "Configure it in backend/.env before using image-to-image."
            )
        if not image_bytes:
            raise ValueError("Cannot run image-to-image without a source image.")

        strength = max(0.05, min(1.0, float(strength)))
        try:
            source = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise ValueError(f"Source image could not be decoded: {type(exc).__name__}: {exc}") from exc

        errors: list[str] = []
        # Some providers reject `strength`; retry without it before failing hard.
        attempt_kwargs: list[dict[str, Any]] = [
            {"model": self.hf_image_to_image_model_id, "prompt": prompt, "strength": strength},
            {"model": self.hf_image_to_image_model_id, "prompt": prompt},
        ]
        for kwargs in attempt_kwargs:
            call_kwargs = dict(kwargs)
            if negative_prompt:
                call_kwargs["negative_prompt"] = negative_prompt
            try:
                image = self.client.image_to_image(source, **call_kwargs)
                return self._image_response_to_png_bytes(image)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

        raise self._image_error(
            RuntimeError(" | ".join(errors[:2])),
            mode="image-to-image",
        )

    def _image_error(self, exc: Exception, *, mode: str) -> RuntimeError:
        if isinstance(exc, PermissionError):
            return RuntimeError(f"HuggingFace image permission denied: {type(exc).__name__}: {exc}")
        if isinstance(exc, TimeoutError):
            return RuntimeError(f"HuggingFace image transient error: {type(exc).__name__}: {exc}")

        message = str(exc).lower()
        if any(term in message for term in ("permission", "unauthorized", "forbidden", "401", "403")):
            category = "permission denied"
        elif any(term in message for term in ("not found", "unsupported", "not supported", "404")):
            category = "unsupported or unavailable model"
        elif any(term in message for term in ("timeout", "temporarily", "unavailable", "503", "rate limit", "429")):
            category = "transient error"
        else:
            category = "request failed"
        return RuntimeError(f"HuggingFace {mode} {category}: {type(exc).__name__}: {exc}")

    def _image_response_to_png_bytes(self, image: Any) -> bytes:
        if image is None:
            raise RuntimeError("HuggingFace image generation returned an empty response.")

        if isinstance(image, bytes):
            if not image:
                raise RuntimeError("HuggingFace image generation returned empty bytes.")
            return image

        if hasattr(image, "save"):
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            data = buffer.getvalue()
            if not data:
                raise RuntimeError("HuggingFace image generation returned an invalid image object.")
            return data

        raise RuntimeError(
            f"HuggingFace image generation returned an unsupported response type: {type(image).__name__}."
        )
