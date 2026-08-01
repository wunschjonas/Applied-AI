from __future__ import annotations

from dataclasses import dataclass


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

    memory_inquiry_markers = {
        "gedächtnis",
        "gedachtnis",
        "gedaechtnis",
        "memory",
        "im rag",
        "dein rag",
        "deinem rag",
        "knowledge base",
        "was steht in",
        "hast du im",
        "gespeichert",
        "hochgeladen",
        "unsere daten",
    }

    def classify_intent(self, message: str) -> AgentIntent:
        normalized = message.lower()

        # Ask-about-memory must win over generic "bild"/"image" keyword matches.
        if self._contains_any(normalized, self.memory_inquiry_markers):
            return AgentIntent(
                use_text=False,
                use_image=False,
                needs_clarification=False,
                label="memory_inquiry",
                decision="Detected a question about stored RAG/memory content.",
                observation="Memory inquiry selected. Answer from memory_search / memory_list.",
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
        use_image = self._contains_any(normalized, self.image_keywords)

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


class ManagerAgent(ManagerIntentClassifier):
    name = "ManagerAgent"
