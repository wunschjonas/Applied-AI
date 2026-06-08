from __future__ import annotations

from huggingface_hub import InferenceClient


class HuggingFaceService:
    def __init__(self, hf_token: str | None, hf_model_id: str):
        if not hf_token:
            raise ValueError("HF_TOKEN is missing. Configure it in backend/.env before calling an agent.")

        self.hf_model_id = hf_model_id
        self.client = InferenceClient(token=hf_token)

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str:
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
