from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.graphs.support import post_data_llm
from app.graphs.support.post_fields import (
    AWAITING_FIELD_KEY,
    FREE_TEXT_FIELDS,
    is_image_motif_briefing,
    is_memory_inquiry,
    is_memory_store_request,
    is_post_status_inquiry,
    is_web_inquiry,
    looks_like_field_briefing,
    wants_generation,
)
from app.services.huggingface_service import HuggingFaceService


@dataclass(frozen=True)
class AgentIntent:
    use_text: bool
    use_image: bool
    needs_clarification: bool
    label: str
    decision: str
    observation: str


_INTENT_META: dict[str, tuple[bool, bool, bool, str]] = {
    # use_text, use_image, needs_clarification, observation
    "post_status_inquiry": (
        False,
        False,
        False,
        "Post status inquiry selected. Answer from posts.json / state.post.",
    ),
    "memory_store": (
        False,
        False,
        False,
        "Memory store selected. Persist fact via memory_store, then confirm.",
    ),
    "memory_inquiry": (
        False,
        False,
        False,
        "Memory inquiry selected. Answer from memory_search / memory_list.",
    ),
    "web_inquiry": (
        False,
        False,
        False,
        "Web inquiry selected. Answer from web_search results only.",
    ),
    "clarification_needed": (
        False,
        False,
        True,
        "Collect post data or clarify; do not run TextAgent/ImageAgent yet.",
    ),
    "image_only": (
        False,
        True,
        False,
        "ImageAgent selected. TextAgent skipped because the user asked for only the image.",
    ),
    "text_only": (
        True,
        False,
        False,
        "TextAgent selected. ImageAgent skipped because the user asked for only text.",
    ),
    "text_and_image": (
        True,
        True,
        False,
        "TextAgent and ImageAgent selected.",
    ),
}


def _intent(
    label: str,
    decision: str,
    *,
    observation: str | None = None,
) -> AgentIntent:
    use_text, use_image, needs_clarification, default_obs = _INTENT_META[label]
    return AgentIntent(
        use_text=use_text,
        use_image=use_image,
        needs_clarification=needs_clarification,
        label=label,
        decision=decision,
        observation=observation or default_obs,
    )


class ManagerIntentClassifier:
    """LLM-first intent; slim explicit-phrase fallback when HF is unavailable."""

    image_only_phrases = {
        "nur bild",
        "nur das bild",
        "nur ein bild",
        "nur bildprompt",
        "nur visual",
        "only image",
        "image only",
        "just image",
        "only the image",
    }
    text_only_phrases = {
        "nur text",
        "nur caption",
        "nur beschreibung",
        "nur hashtags",
        "text only",
        "only text",
    }

    def __init__(
        self,
        hf_factory: Callable[[], HuggingFaceService] | None = None,
    ):
        self.hf_factory = hf_factory

    def classify_intent(
        self,
        message: str,
        post: dict | None = None,
        hf: HuggingFaceService | None = None,
    ) -> AgentIntent:
        service = hf
        if service is None and self.hf_factory is not None:
            service = post_data_llm.try_hf(self.hf_factory)

        llm = post_data_llm.classify_manager_intent_with_llm(
            hf=service,
            user_message=message,
            post=post,
        )
        if llm is not None:
            label = llm["label"]
            if label in _INTENT_META:
                return _intent(label, f"LLM: {llm['decision']}")

        return self._fallback_classify(message, post)

    def _fallback_classify(self, message: str, post: dict | None = None) -> AgentIntent:
        """Deterministic fallback: only explicit action phrases, no topical buzzwords."""
        normalized = message.lower()
        awaiting = (post or {}).get(AWAITING_FIELD_KEY)

        if is_post_status_inquiry(message):
            return _intent(
                "post_status_inquiry",
                "Fallback: explicit question about the current post's stored data.",
            )

        if is_memory_store_request(message):
            return _intent(
                "memory_store",
                "Fallback: explicit request to store a fact in RAG/memory.",
            )

        if is_memory_inquiry(message):
            return _intent(
                "memory_inquiry",
                "Fallback: explicit question about stored RAG/memory content.",
            )

        if not wants_generation(message) and (
            is_image_motif_briefing(message)
            or awaiting in FREE_TEXT_FIELDS
            or looks_like_field_briefing(message)
        ):
            return _intent(
                "clarification_needed",
                "Fallback: Steckbrief field update without generation request.",
                observation="Collect post data only; do not run TextAgent/ImageAgent.",
            )

        if is_web_inquiry(message) and not wants_generation(message):
            return _intent(
                "web_inquiry",
                "Fallback: explicit web/internet search request.",
            )

        if self._contains_any(normalized, self.image_only_phrases):
            return _intent(
                "image_only",
                "Fallback: explicit image-only request.",
            )

        if self._contains_any(normalized, self.text_only_phrases):
            return _intent(
                "text_only",
                "Fallback: explicit text-only request.",
            )

        if wants_generation(message):
            return _intent(
                "text_and_image",
                "Fallback: explicit generate verb — default to text and image.",
            )

        return _intent(
            "clarification_needed",
            "Fallback: no clear action phrase detected.",
            observation="Clarification is required before selecting an agent.",
        )

    def _contains_any(self, normalized_message: str, candidates: set[str]) -> bool:
        return any(candidate in normalized_message for candidate in candidates)
