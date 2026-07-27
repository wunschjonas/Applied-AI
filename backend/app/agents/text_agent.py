from __future__ import annotations

import re
from typing import Any

from app.agents.base_agent import BaseAgent


class TextAgent(BaseAgent):
    name = "TextAgent"

    def generate(
        self,
        task: str,
        trace: dict,
        platform: str | None = "linkedin",
        tone: str | None = "professional",
        target_audience: str | None = None,
        context: str | dict[str, Any] | None = None,
        rag_context: str | None = None,
    ) -> dict[str, Any]:
        self.trace(
            trace,
            decision="Text generation requested.",
            action="build_text_prompt",
            observation=f"Platform={platform or 'unspecified'}, tone={tone or 'unspecified'}.",
        )

        prompt = self._build_prompt(task, platform, tone, target_audience, context, rag_context)
        generated_text = self.hf.generate(
            system_prompt=(
                "You are a practical marketing copywriter. Write concise, useful copy. "
                "Use only the provided brief. Return the final content directly."
            ),
            user_prompt=prompt,
            max_tokens=700,
        )
        hashtags = self._extract_hashtags(generated_text, task)

        self.trace(
            trace,
            decision="HuggingFace returned marketing text.",
            action="return_text_artifact",
            observation=f"Generated {len(generated_text)} characters and {len(hashtags)} hashtags.",
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
        context: str | dict[str, Any] | None,
        rag_context: str | None = None,
    ) -> str:
        context_text = self._context_to_text(context)
        memory_section = f"\n- Memory context: {rag_context}" if rag_context else ""
        return f"""
Create marketing text for this task:
{task}

Details:
- Platform: {platform or "unspecified"}
- Tone: {tone or "professional"}
- Target audience: {target_audience or "unspecified"}
- Context: {context_text}{memory_section}

Include a clear CTA when useful.
Include 3 to 6 relevant hashtags if the platform supports hashtags.
Do not mention that you are an AI.
""".strip()

    def _context_to_text(self, context: str | dict[str, Any] | None) -> str:
        if context is None:
            return "none"
        if isinstance(context, str):
            return context
        return ", ".join(f"{key}: {value}" for key, value in context.items()) or "none"

    def _extract_hashtags(self, generated_text: str, task: str) -> list[str]:
        hashtags = re.findall(r"#\w+", generated_text)

        if hashtags:
            return list(dict.fromkeys(hashtags))[:8]

        words = re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", task)
        fallback = [f"#{word[:32]}" for word in words[:3] if len(word) > 3]
        return fallback or ["#Marketing"]
