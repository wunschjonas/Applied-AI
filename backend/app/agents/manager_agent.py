from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.image_agent import ImageAgent
from app.agents.text_agent import TextAgent


@dataclass(frozen=True)
class AgentIntent:
    use_text: bool
    use_image: bool
    needs_clarification: bool
    label: str
    decision: str
    observation: str


class ManagerAgent(BaseAgent):
    name = "ManagerAgent"

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
        "social media text",
        "linkedin post",
        "instagram caption",
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
    rag_keywords = {
        "rag",
        "source",
        "sources",
        "knowledge",
        "document",
        "documents",
        "retrieval",
        "quelle",
        "quellen",
        "wissen",
        "dokument",
    }

    def chat(self, message: str, trace: dict, context: str | dict[str, Any] | None = None) -> dict[str, Any]:
        context_values = context if isinstance(context, dict) else {}
        intent = self.classify_intent(message)
        self.trace(
            trace,
            decision=intent.decision,
            action="route_to_agents",
            observation=intent.observation,
            status_value="needs_input" if intent.needs_clarification else "success",
        )
        if self._mentions_rag(message):
            self.trace(
                trace,
                decision="The request mentions sources or retrieval.",
                action="skip_rag_for_now",
                observation="RAG is prepared as future work and not used in this version.",
                status_value="skipped",
            )

        if intent.needs_clarification:
            self.trace(
                trace,
                decision="The request is too broad for reliable delegation.",
                action="ask_clarification",
                observation="No specialist agent was called.",
                status_value="needs_input",
            )
            return {
                "assistant_message": (
                    "Should I create marketing text, an image prompt, or both? "
                    "Add the target platform and audience if you already know them."
                ),
                "used_agents": [],
                "generated_artifacts": {},
            }

        artifacts: dict[str, Any] = {}
        used_agents: list[str] = []

        if intent.use_text:
            text_result = TextAgent(self.hf, self.trace_service).generate(
                task=message,
                trace=trace,
                platform=self._platform_from_message(message),
                tone=context_values.get("tone", "professional"),
                target_audience=context_values.get("target_audience"),
                context=context,
            )
            artifacts["text"] = text_result
            used_agents.append("TextAgent")

        if intent.use_image:
            image_result = ImageAgent(self.hf, self.trace_service).generate_prompt(
                task=message,
                trace=trace,
                platform=self._platform_from_message(message),
                visual_style=context_values.get("visual_style"),
                context=context,
            )
            artifacts["image"] = image_result
            used_agents.append("ImageAgent")

        assistant_message = self._summarize_result(message, artifacts, used_agents)
        self.trace(
            trace,
            decision="Specialist agent results are ready.",
            action="compose_manager_response",
            observation=f"Intent={intent.label}. Returned artifacts: {', '.join(artifacts.keys())}.",
        )

        return {
            "assistant_message": assistant_message,
            "used_agents": used_agents,
            "generated_artifacts": artifacts,
        }

    def classify_intent(self, message: str) -> AgentIntent:
        normalized = message.lower()

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
        elif use_text:
            return AgentIntent(
                use_text=True,
                use_image=False,
                needs_clarification=False,
                label="text_only",
                decision="Detected text generation intent.",
                observation="TextAgent selected.",
            )
        elif use_image:
            return AgentIntent(
                use_text=False,
                use_image=True,
                needs_clarification=False,
                label="image_only",
                decision="Detected image prompt intent.",
                observation="ImageAgent selected.",
            )

        return AgentIntent(
            use_text=False,
            use_image=False,
            needs_clarification=True,
            label="clarification",
            decision="No clear text or image intent detected.",
            observation="Clarification is required before selecting an agent.",
        )

    def _decide_route(self, message: str) -> dict[str, Any]:
        intent = self.classify_intent(message)
        return {
            "use_text": intent.use_text,
            "use_image": intent.use_image,
            "needs_clarification": intent.needs_clarification,
            "decision": intent.decision,
            "observation": intent.observation,
        }

    def _platform_from_message(self, message: str) -> str | None:
        normalized = message.lower()
        for platform in ("linkedin", "instagram", "x", "blog", "tiktok", "facebook"):
            if platform in normalized:
                return platform
        return None

    def _mentions_rag(self, message: str) -> bool:
        normalized = message.lower()
        return self._contains_any(normalized, self.rag_keywords)

    def _contains_any(self, normalized_message: str, candidates: set[str]) -> bool:
        return any(candidate in normalized_message for candidate in candidates)

    def _summarize_result(self, message: str, artifacts: dict[str, Any], used_agents: list[str]) -> str:
        image_note = ""
        if "image" in artifacts:
            image_note = (
                "\nImportant image wording rule: The ImageAgent generated an image prompt only. "
                "No actual image file, URL, or base64 image was generated in this backend version."
            )
        summary_prompt = f"""
The user asked:
{message}

Agents used: {", ".join(used_agents)}
Artifacts:
{artifacts}
{image_note}

Write a short manager response for the chat. Mention what was generated and keep it concise.
If an image artifact exists, say that an image prompt was generated and explicitly say that no actual image file was generated in this version.
Never claim that an actual image was created unless the artifacts contain an image file, URL, or base64 image.
""".strip()
        response = self.hf.generate(
            system_prompt="You are the manager agent coordinating marketing specialists.",
            user_prompt=summary_prompt,
            max_tokens=250,
        )
        return self._make_image_wording_safe(response, artifacts)

    def _make_image_wording_safe(self, response: str, artifacts: dict[str, Any]) -> str:
        if "image" not in artifacts:
            return response

        unsafe_phrases = (
            "the image has been created",
            "the image was created",
            "an image has been created",
            "an image was created",
            "das bild wurde erstellt",
            "das bild ist erstellt",
            "ein bild wurde erstellt",
        )
        lowered = response.lower()
        if any(phrase in lowered for phrase in unsafe_phrases):
            response = (
                "Der ImageAgent hat einen Bildprompt erstellt. "
                "Ein echtes Bild wird in dieser Version noch nicht generiert."
            )

        required_note = "Ein echtes Bild wird in dieser Version noch nicht generiert."
        if required_note.lower() not in response.lower():
            response = f"{response}\n\n{required_note}"

        return response
