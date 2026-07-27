from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent


class ImageAgent(BaseAgent):
    name = "ImageAgent"

    def generate_prompt(
        self,
        task: str,
        trace: dict,
        platform: str | None = None,
        visual_style: str | None = None,
        context: str | dict[str, Any] | None = None,
        rag_context: str | None = None,
    ) -> dict[str, Any]:
        self.trace(
            trace,
            decision="Image prompt generation requested.",
            action="build_image_prompt_brief",
            observation=f"Platform={platform or 'unspecified'}, style={visual_style or 'model choice'}.",
        )

        prompt_text = self.hf.generate(
            system_prompt=(
                "You write production-ready image generation prompts for marketing visuals. "
                "Return a strong prompt, a short negative prompt, and a suggested style."
            ),
            user_prompt=self._build_prompt(task, platform, visual_style, context, rag_context),
            max_tokens=500,
        )

        result = {
            "image_prompt": prompt_text,
            "negative_prompt_optional": "low quality, distorted text, blurry, off-brand, cluttered",
            "suggested_style": visual_style or "clean commercial marketing visual",
        }

        self.trace(
            trace,
            decision="HuggingFace returned an image prompt draft.",
            action="return_image_prompt_artifact",
            observation=f"Generated prompt with {len(prompt_text)} characters. Image rendering is future work.",
        )

        return result

    def _build_prompt(
        self,
        task: str,
        platform: str | None,
        visual_style: str | None,
        context: str | dict[str, Any] | None,
        rag_context: str | None = None,
    ) -> str:
        context_text = self._context_to_text(context)
        memory_section = f"\n- Memory context: {rag_context}" if rag_context else ""
        return f"""
Create an image generation prompt for this marketing task:
{task}

Details:
- Platform: {platform or "unspecified"}
- Visual style: {visual_style or "choose an appropriate style"}
- Context: {context_text}{memory_section}

The prompt should describe subject, composition, lighting, colors, mood, and any platform-specific framing.
Do not request readable text inside the image unless explicitly required.
""".strip()

    def _context_to_text(self, context: str | dict[str, Any] | None) -> str:
        if context is None:
            return "none"
        if isinstance(context, str):
            return context
        return ", ".join(f"{key}: {value}" for key, value in context.items()) or "none"
