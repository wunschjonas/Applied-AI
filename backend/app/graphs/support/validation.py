from __future__ import annotations

import re
from typing import Any

from app.graphs.support.delegation import IMAGE_INTENTS, TEXT_INTENTS
from app.services.image_storage_service import ImageStorageService

HASHTAG_PLATFORMS = frozenset({"linkedin", "instagram", "x"})
MIN_TEXT_LENGTH = 180
MIN_HASHTAGS = 3
MIN_IMAGE_PROMPT_LENGTH = 120
MIN_IMAGE_PROMPT_WORDS = 18

META_PREAMBLE_PATTERNS = (
    r"^\s*here is\b",
    r"^\s*here's\b",
    r"^\s*sure[,!]?\b",
    r"^\s*als ki\b",
    r"^\s*as an ai\b",
    r"^\s*of course[,!]?\b",
    r"^\s*i'?ll\b",
    r"```",
)


class ArtifactValidator:
    def __init__(self, image_storage: ImageStorageService):
        self.image_storage = image_storage

    def collect_feedback(
        self,
        intent: str,
        artifacts: dict[str, Any],
        platform: str | None,
        assistant_message: str | None,
    ) -> dict[str, str]:
        feedback: dict[str, str] = {}

        if intent in TEXT_INTENTS:
            issues = self.validate_text(artifacts.get("text"), platform)
            if issues:
                feedback["text"] = "; ".join(issues)

        if intent in IMAGE_INTENTS:
            issues = self.validate_image(artifacts.get("image"))
            if issues:
                feedback["image"] = "; ".join(issues)

        if intent in {"clarification_needed", "memory_inquiry"} and not assistant_message:
            feedback["manager"] = "assistant_message missing"

        return feedback

    def validate_text(self, artifact: dict[str, Any] | None, platform: str | None) -> list[str]:
        if not artifact:
            return ["text artifact missing"]

        issues: list[str] = []
        generated_text = artifact.get("generated_text")
        if not generated_text or not str(generated_text).strip():
            issues.append("generated_text missing")
        else:
            text = str(generated_text).strip()
            if len(text) < MIN_TEXT_LENGTH:
                issues.append("generated_text too short")
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in META_PREAMBLE_PATTERNS):
                issues.append("generated_text contains meta preamble or code fences")
        if "hashtags" not in artifact:
            issues.append("hashtags field missing")
        elif platform and platform.lower() in HASHTAG_PLATFORMS:
            hashtags = artifact.get("hashtags") or []
            if len(hashtags) < MIN_HASHTAGS:
                issues.append(f"need at least {MIN_HASHTAGS} hashtags for {platform}")
        return issues

    def validate_image(self, artifact: dict[str, Any] | None) -> list[str]:
        if not artifact:
            return ["image artifact missing"]

        issues: list[str] = []
        prompt = artifact.get("image_prompt")
        if not prompt or not str(prompt).strip():
            issues.append("image_prompt missing")
        else:
            prompt_text = str(prompt).strip()
            if len(prompt_text) < MIN_IMAGE_PROMPT_LENGTH:
                issues.append("image_prompt too short")
            if len(prompt_text.split()) < MIN_IMAGE_PROMPT_WORDS:
                issues.append("image_prompt too few words")
        if not artifact.get("suggested_style"):
            issues.append("suggested_style missing")
        if artifact.get("partial_success") or artifact.get("image_error"):
            issues.append(f"image generation failed: {artifact.get('image_error', 'unknown error')}")
        if not artifact.get("image_url"):
            issues.append("image_url missing")
        if not artifact.get("image_filename"):
            issues.append("image_filename missing")
        if artifact.get("image_content_type") not in {"image/png"}:
            issues.append("unsupported image_content_type")
        if artifact.get("image_filename") and not self.image_file_available(artifact):
            issues.append("generated image file missing")
        return issues

    def decide(
        self,
        feedback: dict[str, str],
        artifacts: dict[str, Any],
        text_retry_count: int,
        image_retry_count: int,
    ) -> str:
        if not feedback:
            return "valid"

        image_artifact = artifacts.get("image") or {}
        if "text" in feedback and text_retry_count == 0:
            return "retry_text"
        if "image" in feedback and image_retry_count == 0 and image_artifact.get("retryable", True):
            return "retry_image"
        if image_artifact.get("image_prompt") and not self.image_file_available(image_artifact):
            return "partial_success"
        return "failed"

    def image_file_available(self, artifact: dict[str, Any]) -> bool:
        return bool(artifact.get("image_url") and self.image_storage.exists(artifact.get("image_filename")))
