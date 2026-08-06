from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent
from app.graphs.support.manager_tools import GET_POST_DATA_TOOL, ManagerToolDispatcher
from app.graphs.support import post_fields
from app.services.image_storage_service import ImageStorageService


class ImageAgent(BaseAgent):
    name = "ImageAgent"

    def __init__(self, *args, image_storage: ImageStorageService | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.image_storage = image_storage or ImageStorageService()

    def generate_prompt(
        self,
        task: str,
        trace: dict,
        platform: str | None = None,
        visual_style: str | None = None,
        context: str | dict[str, Any] | None = None,
        rag_context: str | None = None,
    ) -> dict[str, Any]:
        self.record(
            trace,
            "image_prompt_start",
            platform=platform,
            visual_style=visual_style,
        )

        prompt_text = self.hf.generate(
            system_prompt=(
                "You write production-ready image generation prompts for marketing visuals. "
                "Stay on the current post topic. Use memory only when it clearly matches that topic; "
                "never invent motifs from unrelated memory. "
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

        self.record(
            trace,
            "image_prompt_done",
            prompt_chars=len(prompt_text),
        )

        return result

    def generate_image(
        self,
        task: str,
        trace: dict,
        platform: str | None = None,
        visual_style: str | None = None,
        context: str | dict[str, Any] | None = None,
        rag_context: str | None = None,
        validation_feedback: str | None = None,
        post_id: str | None = None,
        current_image: bytes | None = None,
        strength: float = 0.65,
        post_repository: Any | None = None,
    ) -> dict[str, Any]:
        """Generate or refine a post image from text.

        When ``current_image`` (or a stored post image) exists, use img2img;
        otherwise text-to-image.
        """
        if current_image is None and post_id:
            current_image = self.image_storage.read_post_image(post_id)

        context = self._enrich_context_from_post(
            context=context,
            post_id=post_id,
            post_repository=post_repository,
            trace=trace,
        )
        tools_called = []
        if isinstance(context, dict):
            tools_called = list(context.pop("tools_called", []) or [])
            if context.get("platform") and not platform:
                platform = str(context["platform"])
            if not visual_style:
                visual_style = context.get("image_style") or context.get("visual_style")
                if visual_style:
                    visual_style = str(visual_style)

        prompt_task = task
        if validation_feedback:
            prompt_task = f"{task}\n\nValidation feedback for retry: {validation_feedback}"

        artifact = self.generate_prompt(
            task=prompt_task,
            trace=trace,
            platform=platform,
            visual_style=visual_style,
            context=context,
            rag_context=rag_context,
        )
        if tools_called:
            artifact["tools_called"] = tools_called

        prompt = artifact.get("image_prompt", "")
        negative_prompt = artifact.get("negative_prompt_optional")
        img2img_bytes = current_image
        img2img_source = "current_post" if img2img_bytes else "none"
        use_img2img = bool(img2img_bytes)
        model_id = (
            getattr(self.hf, "hf_image_to_image_model_id", None)
            if use_img2img
            else getattr(self.hf, "hf_image_model_id", None)
        ) or "unconfigured"

        generation_mode = "text_to_image"
        try:
            if use_img2img:
                self.record(
                    trace,
                    "image_call",
                    image_mode="image_to_image",
                    model_id=model_id,
                    strength=strength,
                    img2img_source=img2img_source,
                )
                try:
                    image_bytes = self.hf.generate_image_from_image(
                        prompt=prompt,
                        image_bytes=img2img_bytes or b"",
                        negative_prompt=negative_prompt,
                        strength=strength,
                    )
                    generation_mode = "image_to_image"
                except Exception as img2img_exc:
                    self.record(
                        trace,
                        "image_fallback",
                        status="warning",
                        error=f"{type(img2img_exc).__name__}: {img2img_exc}",
                    )
                    txt_model = getattr(self.hf, "hf_image_model_id", None) or "unconfigured"
                    self.record(
                        trace,
                        "image_call",
                        image_mode="text_to_image_fallback",
                        model_id=txt_model,
                    )
                    image_bytes = self.hf.generate_image(prompt=prompt, negative_prompt=negative_prompt)
                    generation_mode = "text_to_image_fallback"
                    artifact["image_to_image_error"] = f"{type(img2img_exc).__name__}: {img2img_exc}"
            else:
                self.record(
                    trace,
                    "image_call",
                    image_mode="text_to_image",
                    model_id=model_id,
                )
                image_bytes = self.hf.generate_image(prompt=prompt, negative_prompt=negative_prompt)

            self.record(trace, "image_store")
            stored = self.image_storage.save_png(image_bytes, filename_stem=post_id)
            artifact.update(stored)
            artifact["generation_mode"] = generation_mode
            artifact["img2img_source"] = img2img_source
            artifact["used_current_image"] = bool(current_image)
            if use_img2img:
                artifact["used_image_to_image"] = generation_mode == "image_to_image"
                artifact["image_to_image_strength"] = strength

            self.record(
                trace,
                "image_return",
                image_filename=stored.get("image_filename"),
                image_url=stored.get("image_url"),
                image_mode=generation_mode,
                img2img_source=img2img_source,
            )
            return artifact
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            artifact.update(
                {
                    "image_url": None,
                    "image_filename": None,
                    "image_content_type": None,
                    "image_error": error,
                    "partial_success": True,
                    "retryable": self._is_retryable_error(error),
                    "generation_mode": generation_mode,
                    "img2img_source": img2img_source,
                    "used_current_image": bool(current_image),
                }
            )
            self.record(
                trace,
                "image_return",
                status="partial_success",
                error=error,
                image_mode=generation_mode,
            )
            return artifact

    def _enrich_context_from_post(
        self,
        *,
        context: str | dict[str, Any] | None,
        post_id: str | None,
        post_repository: Any | None,
        trace: dict,
    ) -> dict[str, Any]:
        """Load Steckbrief from posts.json and optionally via get_post_data tool."""
        merged: dict[str, Any] = {}
        if isinstance(context, dict):
            merged.update({k: v for k, v in context.items() if v})
        elif isinstance(context, str) and context.strip():
            merged["request_context"] = context.strip()

        post = None
        if post_repository is not None and post_id:
            try:
                post = post_repository.get(post_id)
            except Exception:
                post = None
        if post:
            for key in (
                "topic",
                "platform",
                "target_audience",
                "tone_of_voice",
                "text_context",
                "text_length",
                "image_context",
                "image_style",
            ):
                if post.get(key) and key not in merged:
                    merged[key] = post[key]
            if post.get("image_style") and not merged.get("visual_style"):
                merged["visual_style"] = post["image_style"]

        tool_summary = self._call_get_post_data_tool(
            post_id=post_id,
            post=post,
            post_repository=post_repository,
            trace=trace,
        )
        if tool_summary:
            merged["post_steckbrief"] = tool_summary
            artifact_tools = merged.setdefault("tools_called", [])
            if isinstance(artifact_tools, list) and "get_post_data" not in artifact_tools:
                artifact_tools.append("get_post_data")

        return merged

    def _call_get_post_data_tool(
        self,
        *,
        post_id: str | None,
        post: dict[str, Any] | None,
        post_repository: Any | None,
        trace: dict,
    ) -> str | None:
        """Ask the LLM to call get_post_data; always dispatch if chosen (or force once)."""
        dispatcher = ManagerToolDispatcher(
            rag_service=None,
            post_repository=post_repository,
            web_search=None,
        )
        state = {"post_id": post_id, "post": post}

        try:
            result = self.hf.chat_with_tools(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the ImageAgent tool planner. "
                            "Call get_post_data exactly once to read the marketing post Steckbrief "
                            "(topic, platform, audience, tone, text_context, text_length, "
                            "image_context, image_style) from storage."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Load the Steckbrief for post_id={post_id or 'unknown'} "
                            "with get_post_data before generating the image."
                        ),
                    },
                ],
                tools=[GET_POST_DATA_TOOL],
                max_tokens=200,
                temperature=0.1,
            )
        except Exception as exc:
            self.record(
                trace,
                "image_tool_get_post_data",
                status="skipped",
                error=f"{type(exc).__name__}: {exc}",
            )
            # Deterministic fallback observation from local post
            if post:
                summary = post_fields.post_status_summary(post)
                self.record(
                    trace,
                    "image_tool_get_post_data",
                    status="success",
                    tool_name="get_post_data",
                    detail="fallback_from_repository",
                )
                return summary
            return None

        tool_calls = result.get("tool_calls") or []
        called = False
        observation = None
        for call in tool_calls:
            name = call.get("name") or ""
            if name != "get_post_data":
                continue
            called = True
            observation, status, effects = dispatcher.dispatch(
                "get_post_data",
                call.get("arguments") or {},
                state,
            )
            self.record(
                trace,
                "image_tool_get_post_data",
                status=status,
                tool_name="get_post_data",
                detail=(effects.get("post_data_summary") or observation or "")[:240],
            )
            break

        if not called and post:
            observation, status, effects = dispatcher.dispatch("get_post_data", {}, state)
            self.record(
                trace,
                "image_tool_get_post_data",
                status=status,
                tool_name="get_post_data",
                detail="forced_dispatch;" + ((effects.get("post_data_summary") or "")[:200]),
            )
        return observation

    def _build_prompt(
        self,
        task: str,
        platform: str | None,
        visual_style: str | None,
        context: str | dict[str, Any] | None,
        rag_context: str | None = None,
    ) -> str:
        context_text = self._context_to_text(context)
        image_motif = ""
        tone = None
        style_from_context = None
        if isinstance(context, dict):
            if context.get("image_context"):
                image_motif = f"\n- Image motif (image_context): {context['image_context']}"
            style_from_context = context.get("image_style") or context.get("visual_style")
            tone = context.get("tone") or context.get("tone_of_voice")
        effective_style = visual_style or style_from_context
        tone_line = f"\n- Mood / tone of voice: {tone}" if tone else ""
        memory_section = f"\n- Memory context: {rag_context}" if rag_context else ""
        tone_rule = ""
        if tone:
            tone_rule = (
                "\n- Match the emotional tone of the marketing copy "
                "(e.g. proud/stolz → heroic; casual/locker → light, friendly; "
                "professional → clean, polished) while respecting image_style."
            )
        return f"""
Create an image generation prompt for this marketing task:
{task}

Details:
- Platform: {platform or "unspecified"}
- Visual style: {effective_style or "choose an appropriate style"}{tone_line}
- Context: {context_text}{image_motif}{memory_section}

Rules:
- The visual must match the current post topic from the task/brief.
- Prefer image_context / Bildmotiv when provided — that is the intended scene.
- Prefer image_style / Bildstil when provided — that is the intended look.{tone_rule}
- Use Memory context only when it clearly relates to that topic; ignore unrelated memories.
- Do not mix in motifs from off-topic memory.
The prompt should describe subject, composition, lighting, colors, mood, and any platform-specific framing.
Do not request readable text inside the image unless explicitly required.
""".strip()

    def _context_to_text(self, context: str | dict[str, Any] | None) -> str:
        if context is None:
            return "none"
        if isinstance(context, str):
            return context
        return ", ".join(f"{key}: {value}" for key, value in context.items()) or "none"

    def _is_retryable_error(self, error: str) -> bool:
        lowered = error.lower()
        transient_terms = ("transient", "timeout", "temporarily", "unavailable", "503", "429", "rate limit")
        permanent_terms = (
            "hf_token",
            "permission",
            "forbidden",
            "unauthorized",
            "unsupported",
            "not found",
            "invalid configuration",
        )
        return any(term in lowered for term in transient_terms) and not any(
            term in lowered for term in permanent_terms
        )
