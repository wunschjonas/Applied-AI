from __future__ import annotations

from io import BytesIO
from typing import Any

from huggingface_hub import InferenceClient


class HuggingFaceService:
    def __init__(self, hf_token: str | None, hf_model_id: str, hf_image_model_id: str | None = None):
        if not hf_token:
            raise ValueError("HF_TOKEN is missing. Configure it in backend/.env before calling an agent.")

        self.hf_model_id = hf_model_id
        self.hf_image_model_id = hf_image_model_id
        self.client = InferenceClient(token=hf_token)

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

    def generate_image(self, prompt: str, negative_prompt: str | None = None) -> bytes:
        if not self.hf_image_model_id:
            raise ValueError("HF_IMAGE_MODEL_ID is missing. Configure it in backend/.env before generating images.")

        try:
            kwargs: dict[str, Any] = {"model": self.hf_image_model_id}
            if negative_prompt:
                kwargs["negative_prompt"] = negative_prompt
            image = self.client.text_to_image(prompt, **kwargs)
        except PermissionError as exc:
            raise RuntimeError(f"HuggingFace image permission denied: {type(exc).__name__}: {exc}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"HuggingFace image transient error: {type(exc).__name__}: {exc}") from exc
        except Exception as exc:
            message = str(exc).lower()
            if any(term in message for term in ("permission", "unauthorized", "forbidden", "401", "403")):
                category = "permission denied"
            elif any(term in message for term in ("not found", "unsupported", "not supported", "404")):
                category = "unsupported or unavailable model"
            elif any(term in message for term in ("timeout", "temporarily", "unavailable", "503", "rate limit", "429")):
                category = "transient error"
            else:
                category = "request failed"
            raise RuntimeError(f"HuggingFace image {category}: {type(exc).__name__}: {exc}") from exc

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

        raise RuntimeError(f"HuggingFace image generation returned an unsupported response type: {type(image).__name__}.")
