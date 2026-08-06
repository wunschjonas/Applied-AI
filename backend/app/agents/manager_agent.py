from __future__ import annotations

import re
from dataclasses import dataclass

from app.graphs.support.post_fields import (
    AWAITING_FIELD_KEY,
    FREE_TEXT_FIELDS,
    is_image_motif_briefing,
    is_memory_inquiry,
    is_memory_store_request,
    is_post_status_inquiry,
    is_web_inquiry,
    wants_generation,
)


@dataclass(frozen=True)
class AgentIntent:
    use_text: bool
    use_image: bool
    needs_clarification: bool
    label: str
    decision: str
    observation: str


class ManagerIntentClassifier:
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
    text_keywords = {
        "caption",
        "hashtags",
        "hashtag",
        "description",
        "text",
        "copy",
        "cta",
        "tweet",
        "blog",
        "write",
        "writing",
        "beschreibung",
        "untertitel",
        "post text",
        "post",
        "social media post",
        "social media text",
        "linkedin post",
        "instagram caption",
        "linkedin",
    }
    image_keywords = {
        "image",
        "visual",
        "picture",
        "graphic",
        "design",
        "thumbnail",
        "banner",
        "photo",
        "prompt",
        "bild",
        "bildprompt",
        "bildidee",
        "grafik",
        "visuell",
        "visualisierung",
    }

    def classify_intent(self, message: str, post: dict | None = None) -> AgentIntent:
        normalized = message.lower()
        awaiting = (post or {}).get(AWAITING_FIELD_KEY)

        # Current-post status questions win over generic knowledge / keyword matches.
        if is_post_status_inquiry(message):
            return AgentIntent(
                use_text=False,
                use_image=False,
                needs_clarification=False,
                label="post_status_inquiry",
                decision="Detected a question about the current post's stored data.",
                observation="Post status inquiry selected. Answer from posts.json / state.post.",
            )

        # Explicit store requests must not be treated as memory Q&A.
        if is_memory_store_request(message):
            return AgentIntent(
                use_text=False,
                use_image=False,
                needs_clarification=False,
                label="memory_store",
                decision="Detected an explicit request to store a fact in RAG/memory.",
                observation="Memory store selected. Persist fact via memory_store, then confirm.",
            )

        # Ask-about-memory must win over generic "bild"/"image" keyword matches.
        if is_memory_inquiry(message):
            return AgentIntent(
                use_text=False,
                use_image=False,
                needs_clarification=False,
                label="memory_inquiry",
                decision="Detected a question about stored RAG/memory content.",
                observation="Memory inquiry selected. Answer from memory_search / memory_list.",
            )

        # Pure web/current-events questions (not "schreibe einen Post …").
        if is_web_inquiry(message) and not wants_generation(message):
            return AgentIntent(
                use_text=False,
                use_image=False,
                needs_clarification=False,
                label="web_inquiry",
                decision="Detected a question about current public/web information.",
                observation="Web inquiry selected. Answer from web_search results only.",
            )

        # Filling Steckbrief (esp. Bildmotiv) must not trigger ImageAgent via "bild*".
        if not wants_generation(message) and (
            is_image_motif_briefing(message)
            or awaiting in FREE_TEXT_FIELDS
        ):
            return AgentIntent(
                use_text=False,
                use_image=False,
                needs_clarification=True,
                label="clarification_needed",
                decision="Detected Steckbrief field update without generation request.",
                observation="Collect post data only; do not run TextAgent/ImageAgent.",
            )

        if self._contains_any(normalized, self.image_only_phrases):
            return AgentIntent(
                use_text=False,
                use_image=True,
                needs_clarification=False,
                label="image_only",
                decision="Detected explicit image-only intent.",
                observation="ImageAgent selected. TextAgent skipped because the user asked for only the image.",
            )

        if self._contains_any(normalized, self.text_only_phrases):
            return AgentIntent(
                use_text=True,
                use_image=False,
                needs_clarification=False,
                label="text_only",
                decision="Detected explicit text-only intent.",
                observation="TextAgent selected. ImageAgent skipped because the user asked for only text.",
            )

        use_text = self._contains_any(normalized, self.text_keywords)
        use_image = self._contains_image_keyword(normalized)

        # Keyword hits alone are ambiguous — confirm before TextAgent/ImageAgent.
        # Explicit generate verbs (erstell/schreib/…) or nur-text/nur-bild phrases proceed.
        if (use_text or use_image) and not wants_generation(message):
            return AgentIntent(
                use_text=False,
                use_image=False,
                needs_clarification=True,
                label="clarification_needed",
                decision="Detected text/image keywords without an explicit generate request.",
                observation="Ask whether to create text, image, or both before running agents.",
            )

        if use_text and use_image:
            return AgentIntent(
                use_text=True,
                use_image=True,
                needs_clarification=False,
                label="text_and_image",
                decision="Detected both text and image intent.",
                observation="TextAgent and ImageAgent selected.",
            )
        if use_text:
            return AgentIntent(
                use_text=True,
                use_image=False,
                needs_clarification=False,
                label="text_only",
                decision="Detected text generation intent.",
                observation="TextAgent selected.",
            )
        if use_image:
            return AgentIntent(
                use_text=False,
                use_image=True,
                needs_clarification=False,
                label="image_only",
                decision="Detected image generation intent.",
                observation="ImageAgent selected.",
            )

        return AgentIntent(
            use_text=False,
            use_image=False,
            needs_clarification=True,
            label="clarification_needed",
            decision="No clear text or image intent detected.",
            observation="Clarification is required before selecting an agent.",
        )

    def _contains_any(self, normalized_message: str, candidates: set[str]) -> bool:
        return any(candidate in normalized_message for candidate in candidates)

    def _contains_image_keyword(self, normalized_message: str) -> bool:
        """Match image keywords; keep 'bild' as a whole word so 'bildmotiv' does not count."""
        for candidate in self.image_keywords:
            if candidate == "bild":
                if re.search(r"(?<!\w)bild(?!\w)", normalized_message):
                    return True
            elif candidate in normalized_message:
                return True
        return False
