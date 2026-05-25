from __future__ import annotations

from datetime import datetime
from typing import Any

from huggingface_hub import InferenceClient


class ManagerAgent:
    def __init__(self, hf_token: str | None, hf_model_id: str):
        if not hf_token:
            raise ValueError("HF_TOKEN is missing. Please configure it in backend/.env.")

        self.hf_model_id = hf_model_id
        self.client = InferenceClient(token=hf_token)

    def run(self, post: dict[str, Any]) -> dict[str, Any]:
        trace: list[dict[str, Any]] = []

        trace.append(self._trace(
            thought="I need to understand the post briefing before writing content.",
            action="analyze_briefing",
            observation="The briefing is being analyzed.",
        ))
        analysis = self._analyze_briefing(post)

        trace.append(self._trace(
            thought="Now I need a reusable post structure with hook, main message, CTA and hashtags.",
            action="create_post_structure",
            observation=f"Analysis result: {analysis}",
        ))
        post_structure = self._create_post_structure(analysis)

        trace.append(self._trace(
            thought="Now I can ask the language model to generate the final preview text.",
            action="generate_preview_with_huggingface",
            observation=f"Post structure created: {post_structure}",
        ))
        generated_text = self._generate_text(post, analysis, post_structure)

        preview = {
            "generated_text": generated_text,
            "post_structure": post_structure,
            "hashtags": post_structure["hashtags"],
            "image_prompt_optional": post_structure["image_prompt_optional"],
            "created_at": datetime.utcnow().isoformat(),
        }

        trace.append(self._trace(
            thought="The preview is generated. I now return the preview and trace for review.",
            action="return_preview",
            observation="Preview generation completed.",
        ))

        return {
            "preview": preview,
            "agent_trace": trace,
        }

    def _analyze_briefing(self, post: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": (
                f"Create a {post['tone_of_voice']} {post['platform']} post about "
                f"{post['topic']} for {post['target_audience']}. "
                f"The goal is: {post['goal']}."
            ),
            "topic": post["topic"],
            "platform": post["platform"],
            "target_audience": post["target_audience"],
            "tone_of_voice": post["tone_of_voice"],
            "goal": post["goal"],
            "additional_context": post.get("additional_context") or "",
        }

    def _create_post_structure(self, analysis: dict[str, Any]) -> dict[str, Any]:
        hashtag_base = analysis["topic"].replace(" ", "").replace("-", "").lower()

        return {
            "hook": f"Why {analysis['topic']} matters now",
            "main_message": (
                f"Explain the relevance of {analysis['topic']} for "
                f"{analysis['target_audience']} in a clear and useful way."
            ),
            "cta": "What do you think about this approach?",
            "hashtags": [
                f"#{hashtag_base}",
                f"#{analysis['platform']}Marketing",
                "#AppliedAI",
            ],
            "image_prompt_optional": (
                f"Professional visual for a {analysis['platform']} post about "
                f"{analysis['topic']} for {analysis['target_audience']}"
            ),
        }

    def _generate_text(
        self,
        post: dict[str, Any],
        analysis: dict[str, Any],
        post_structure: dict[str, Any],
    ) -> str:
        prompt = self._build_prompt(post, analysis, post_structure)

        response = self.client.chat_completion(
            model=self.hf_model_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional marketing assistant. "
                        "Write concise, platform-aware social media posts. "
                        "Do not invent facts. Use only the provided briefing."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            max_tokens=500,
            temperature=0.7,
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError("HuggingFace returned an empty response.")

        return content.strip()

    def _build_prompt(
        self,
        post: dict[str, Any],
        analysis: dict[str, Any],
        post_structure: dict[str, Any],
    ) -> str:
        return f"""
Create one social media post preview.

Post briefing:
- Title: {post["title"]}
- Topic: {post["topic"]}
- Platform: {post["platform"]}
- Target audience: {post["target_audience"]}
- Tone of voice: {post["tone_of_voice"]}
- Goal: {post["goal"]}
- Additional context: {post.get("additional_context") or "None"}

Analysis:
{analysis["summary"]}

Required structure:
- Hook: {post_structure["hook"]}
- Main message: {post_structure["main_message"]}
- CTA: {post_structure["cta"]}
- Hashtags: {", ".join(post_structure["hashtags"])}

Rules:
- Write in German.
- Make it suitable for the selected platform.
- Keep it concise.
- Include the hashtags at the end.
- Do not mention that you are an AI.
""".strip()

    def _trace(self, thought: str, action: str, observation: str) -> dict[str, Any]:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "thought": thought,
            "action": action,
            "observation": observation,
        }