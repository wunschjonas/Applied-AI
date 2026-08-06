from __future__ import annotations

import re
from typing import Any

from app.agents.base_agent import BaseAgent
from app.graphs.support.language import GERMAN_COPY_RULE, contains_non_german_script
from app.graphs.support.post_fields import normalize_text_length_guidance

_TEXT_SYSTEM = (
    "You are a practical German marketing copywriter. "
    f"{GERMAN_COPY_RULE} "
    "Write concise, useful copy. Use only the provided brief and ONLY memory facts "
    "that clearly match the current post topic. Ignore unrelated memory. "
    "Return the final marketing content directly — no preamble."
)


class TextAgent(BaseAgent):
    name = "TextAgent"

    def generate(
        self,
        task: str,
        trace: dict,
        platform: str | None = "linkedin",
        tone: str | None = "professional",
        target_audience: str | None = None,
        text_context: str | None = None,
        text_length: str | None = None,
        context: str | dict[str, Any] | None = None,
        rag_context: str | None = None,
        validation_feedback: str | None = None,
    ) -> dict[str, Any]:
        self.record(
            trace,
            "text_build_prompt",
            platform=platform,
            tone=tone,
        )

        if isinstance(context, dict):
            text_context = text_context or context.get("text_context")
            text_length = text_length or context.get("text_length")

        prompt = self._build_prompt(
            task,
            platform,
            tone,
            target_audience,
            text_context,
            text_length,
            context,
            rag_context,
            validation_feedback,
        )
        self.record(
            trace,
            "text_call_model",
            model_id=getattr(self.hf, "hf_model_id", None) or "unknown",
        )
        generated_text = self.hf.generate(
            system_prompt=_TEXT_SYSTEM,
            user_prompt=prompt,
            max_tokens=700,
        )
        # One repair pass if the model drifted into Chinese/other scripts.
        if contains_non_german_script(generated_text):
            self.record(trace, "text_language_repair", detail="non-german script detected")
            generated_text = self.hf.generate(
                system_prompt=_TEXT_SYSTEM,
                user_prompt=(
                    f"{prompt}\n\n"
                    "IMPORTANT: Your previous draft used a non-German script. "
                    "Rewrite the entire post and all hashtags in German only "
                    "(Latin letters; German umlauts allowed)."
                ),
                max_tokens=700,
                temperature=0.4,
            )
        self.record(
            trace,
            "text_parse",
            text_chars=len(generated_text),
        )
        hashtags = self._extract_hashtags(generated_text, task)

        self.record(
            trace,
            "text_return",
            text_chars=len(generated_text),
            hashtag_count=len(hashtags),
        )

        return {
            "generated_text": generated_text,
            "hashtags": hashtags,
        }

    def _build_prompt(
        self,
        task: str,
        platform: str | None,
        tone: str | None,
        target_audience: str | None,
        text_context: str | None,
        text_length: str | None,
        context: str | dict[str, Any] | None,
        rag_context: str | None = None,
        validation_feedback: str | None = None,
    ) -> str:
        context_text = self._context_to_text(context)
        memory_section = f"\n- Memory context: {rag_context}" if rag_context else ""
        feedback_section = f"\n- Validation feedback to fix: {validation_feedback}" if validation_feedback else ""
        length_guidance = normalize_text_length_guidance(text_length)
        length_detail = text_length or "unspecified"
        length_rule = f"\n- Length requirement (mandatory): {length_guidance}" if length_guidance else ""
        return f"""
Create marketing text for this task:
{task}

Details:
- Platform: {platform or "unspecified"}
- Tone: {tone or "professional"}
- Target audience: {target_audience or "unspecified"}
- Text focus (text_context): {text_context or "unspecified"}
- Text length request: {length_detail}
- Context: {context_text}{memory_section}{feedback_section}

Rules:
- {GERMAN_COPY_RULE}
- Stay on the current post topic from the task/brief.
- Cover the text_context / key message when provided.
- Use Memory context only when it clearly relates to that topic; ignore off-topic memory.{length_rule}
Include a clear CTA when useful.
Include 3 to 6 relevant German/Latin hashtags if the platform supports hashtags.
Do not mention that you are an AI.
""".strip()

    def _context_to_text(self, context: str | dict[str, Any] | None) -> str:
        if context is None:
            return "none"
        if isinstance(context, str):
            return context
        return ", ".join(f"{key}: {value}" for key, value in context.items()) or "none"

    def _extract_hashtags(self, generated_text: str, task: str) -> list[str]:
        # Prefer Latin/German hashtags; drop CJK or other non-Latin tags.
        raw = re.findall(r"#[A-Za-zÄÖÜäöüß0-9_]+", generated_text or "")
        hashtags = [tag for tag in raw if not contains_non_german_script(tag)]

        if hashtags:
            return list(dict.fromkeys(hashtags))[:8]

        words = re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", task)
        fallback = [f"#{word[:32]}" for word in words[:3] if len(word) > 3]
        return fallback or ["#Marketing"]
