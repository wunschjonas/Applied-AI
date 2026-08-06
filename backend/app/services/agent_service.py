from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status

from app.agents.image_agent import ImageAgent
from app.agents.text_agent import TextAgent
from app.core.config import settings
from app.graphs.dependencies import record_trace_event
from app.graphs.manager_chat_graph import ManagerChatGraph
from app.graphs.support import messages
from app.graphs.support.post_data_llm import compose_specialist_reply
from app.graphs.support.delegation import build_image_refine_task, build_text_refine_task
from app.graphs.support.tao_composer import TaoEvent, compose
from app.metrics import inc_manager_chat_request
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.log_service import LogService
from app.services.post_repository import PostRepository
from app.services.rag_service import RAGService
from app.services.trace_service import TraceService


class AgentService:
    def __init__(self):
        self.chat_service = ChatService()
        self.trace_service = TraceService()
        self.rag_service = RAGService(memory_url=settings.mcp_memory_url)
        self.log_service = LogService()
        self.post_repository = PostRepository()

    def manager_chat(
        self,
        message: str,
        post_id: str,
        context: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            self._require_post(post_id)
            graph = ManagerChatGraph(
                chat_service=self.chat_service,
                trace_service=self.trace_service,
                rag_service=self.rag_service,
                hf_factory=self._hf,
                log_service=self.log_service,
                post_repository=self.post_repository,
            )
            return graph.run(message=message, post_id=post_id, context=context)
        except Exception as exc:
            if not isinstance(exc, HTTPException):
                inc_manager_chat_request("exception")
            raise self._to_http_error(exc) from exc

    def _require_post(self, post_id: str) -> dict[str, Any]:
        post = self.post_repository.get(post_id)
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )
        return post

    def generate_text(
        self,
        task: str,
        platform: str | None,
        tone: str | None,
        target_audience: str | None,
        context: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        trace = self.trace_service.create_trace(metadata={"entrypoint": "direct_text_agent"})
        t0 = datetime.utcnow()
        try:
            result = TextAgent(self._hf(), self.trace_service).generate(
                task=task,
                trace=trace,
                platform=platform,
                tone=tone,
                target_audience=target_audience,
                context=context,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            event = TaoEvent(
                phase="direct_error",
                node="TextAgent",
                agent="TextAgent",
                status="error",
                facts={"artifact_type": "Text", "error": error},
            )
            triple = record_trace_event(self.trace_service, trace, event)
            self.log_service.add_log(
                agent="text_agent",
                action="direct_generate_text",
                input_summary=task,
                status="error",
                duration_ms=self._ms(t0),
                run_id=trace["trace_id"],
                step="generate_text",
                tool_called="huggingface_generate_text",
                thought=triple.thought,
                observation=triple.observation,
                output_summary=error,
            )
            raise self._to_http_error(exc) from exc

        done = compose(
            TaoEvent(
                phase="text_return",
                node="TextAgent",
                agent="TextAgent",
                facts={
                    "text_chars": len(result.get("generated_text", "")),
                    "hashtag_count": len(result.get("hashtags", [])),
                },
            )
        )
        self.log_service.add_log(
            agent="text_agent",
            action="direct_generate_text",
            input_summary=task,
            status="success",
            duration_ms=self._ms(t0),
            run_id=trace["trace_id"],
            step="generate_text",
            tool_called="huggingface_generate_text",
            thought=done.thought,
            observation=done.observation,
            output_summary=f"{len(result.get('generated_text', ''))} chars generated",
        )
        return {**result, "trace_id": trace["trace_id"]}

    def generate_image_prompt(
        self,
        task: str,
        platform: str | None,
        visual_style: str | None,
        context: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        trace = self.trace_service.create_trace(metadata={"entrypoint": "direct_image_agent"})
        t0 = datetime.utcnow()
        try:
            result = ImageAgent(self._hf(), self.trace_service).generate_prompt(
                task=task,
                trace=trace,
                platform=platform,
                visual_style=visual_style,
                context=context,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            event = TaoEvent(
                phase="direct_error",
                node="ImageAgent",
                agent="ImageAgent",
                status="error",
                facts={"artifact_type": "Bildprompt", "error": error},
            )
            triple = record_trace_event(self.trace_service, trace, event)
            self.log_service.add_log(
                agent="image_agent",
                action="direct_generate_image_prompt",
                input_summary=task,
                status="error",
                duration_ms=self._ms(t0),
                run_id=trace["trace_id"],
                step="generate_image_prompt",
                tool_called="huggingface_generate_text",
                thought=triple.thought,
                observation=triple.observation,
                output_summary=error,
            )
            raise self._to_http_error(exc) from exc

        done = compose(
            TaoEvent(
                phase="image_prompt_done",
                node="ImageAgent",
                agent="ImageAgent",
                facts={"prompt_chars": len(result.get("image_prompt", ""))},
            )
        )
        self.log_service.add_log(
            agent="image_agent",
            action="direct_generate_image_prompt",
            input_summary=task,
            status="success",
            duration_ms=self._ms(t0),
            run_id=trace["trace_id"],
            step="generate_image_prompt",
            tool_called="huggingface_generate_text",
            thought=done.thought,
            observation=done.observation,
            output_summary=f"Image prompt: {len(result.get('image_prompt', ''))} chars",
        )
        return {**result, "trace_id": trace["trace_id"]}

    def generate_image(
        self,
        task: str,
        platform: str | None,
        visual_style: str | None,
        context: str | dict[str, Any] | None,
        post_id: str | None = None,
    ) -> dict[str, Any]:
        trace = self.trace_service.create_trace(metadata={"entrypoint": "direct_image_agent_generate"})
        t0 = datetime.utcnow()
        try:
            result = ImageAgent(self._hf(), self.trace_service).generate_image(
                task=task,
                trace=trace,
                platform=platform,
                visual_style=visual_style,
                context=context,
                post_id=post_id,
                post_repository=self.post_repository,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            event = TaoEvent(
                phase="direct_error",
                node="ImageAgent",
                agent="ImageAgent",
                status="error",
                facts={"artifact_type": "Bild", "error": error},
            )
            triple = record_trace_event(self.trace_service, trace, event)
            self.log_service.add_log(
                agent="image_agent",
                action="direct_generate_image",
                input_summary=task,
                status="error",
                duration_ms=self._ms(t0),
                run_id=trace["trace_id"],
                step="generate_image",
                tool_called="huggingface_text_to_image",
                thought=triple.thought,
                observation=triple.observation,
                output_summary=error,
            )
            raise self._to_http_error(exc) from exc

        done = compose(
            TaoEvent(
                phase="image_return",
                node="ImageAgent",
                agent="ImageAgent",
                status="success" if result.get("image_url") else "partial_success",
                facts={
                    "image_filename": result.get("image_filename"),
                    "image_url": result.get("image_url"),
                    "image_mode": result.get("generation_mode") or "text_to_image",
                    "img2img_source": result.get("img2img_source") or "none",
                    "error": result.get("image_error"),
                },
            )
        )
        self.log_service.add_log(
            agent="image_agent",
            action="direct_generate_image",
            input_summary=task,
            status="success" if result.get("image_url") else "error",
            duration_ms=self._ms(t0),
            run_id=trace["trace_id"],
            step="generate_image",
            tool_called="huggingface_text_to_image",
            thought=done.thought,
            observation=done.observation,
            output_summary=f"image_url={result.get('image_url')}; error={result.get('image_error')}",
        )
        return {**result, "trace_id": trace["trace_id"]}

    def _hf(self) -> HuggingFaceService:
        hf_token = settings.hf_token.get_secret_value() if settings.hf_token else None
        return HuggingFaceService(
            hf_token=hf_token,
            hf_model_id=settings.hf_model_id,
            hf_image_model_id=settings.hf_image_model_id,
            hf_caption_model_id=settings.hf_caption_model_id,
            hf_image_to_image_model_id=settings.hf_image_to_image_model_id,
        )

    def _to_http_error(self, exc: Exception) -> HTTPException:
        if isinstance(exc, HTTPException):
            return exc

        message = str(exc)
        if isinstance(exc, ValueError) and (
            "HF_TOKEN" in message or "Configure it in backend/.env" in message
        ):
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="HuggingFace is not configured (HF_TOKEN missing).",
            )

        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {type(exc).__name__}",
        )

    def text_agent_chat(self, message: str, post_id: str) -> dict[str, Any]:
        """Refine the stored marketing copy: regenerate it and write it back to the post preview."""
        t0 = datetime.utcnow()
        post = self._require_post(post_id)
        chat = self.chat_service.get_or_create_chat(post_id, agent="text_agent")
        self.chat_service.add_message(chat, role="USER", content=message)

        preview = post.get("preview") or {}
        trace = self.trace_service.create_trace(
            chat_id=chat["id"],
            metadata={"entrypoint": "text_agent_chat", "post_id": post_id},
        )
        task = build_text_refine_task(message, preview.get("generated_text"))

        try:
            result = TextAgent(self._hf(), self.trace_service).generate(
                task=task,
                trace=trace,
                platform=post.get("platform"),
                tone=post.get("tone_of_voice") or "professional",
                target_audience=post.get("target_audience"),
                text_context=post.get("text_context"),
                text_length=post.get("text_length"),
                context={
                    "text_context": post.get("text_context"),
                    "text_length": post.get("text_length"),
                    "topic": post.get("topic"),
                },
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            fail = compose(
                TaoEvent(
                    phase="direct_error",
                    node="TextAgent",
                    agent="TextAgent",
                    status="error",
                    facts={"artifact_type": "Text", "error": error},
                )
            )
            self.log_service.add_log(
                agent="text_agent", action="text_chat", input_summary=message,
                status="error", duration_ms=self._ms(t0), run_id=trace["trace_id"],
                step="refine_text", tool_called="huggingface_generate_text",
                thought=fail.thought,
                observation=fail.observation,
                output_summary=error,
            )
            raise self._to_http_error(exc) from exc

        generated_text = result.get("generated_text", "")
        if post:
            self.post_repository.merge_preview(
                post_id,
                {"generated_text": generated_text, "hashtags": result.get("hashtags", [])},
            )

        hf = self._hf()
        ack = compose_specialist_reply(
            role="text",
            hf=hf,
            fallback=messages.TEXT_REFINED,
            situation="The marketing text was regenerated and saved to the post preview.",
            user_message=message,
            post=post,
            artifact_summary=(
                f"{len(generated_text)} chars, {len(result.get('hashtags', []))} hashtags"
            ),
        )
        reply = ack
        self.chat_service.add_message(chat, role="AGENT", content=reply)
        done = compose(
            TaoEvent(
                phase="text_return",
                node="TextAgent",
                agent="TextAgent",
                facts={
                    "text_chars": len(generated_text),
                    "hashtag_count": len(result.get("hashtags", [])),
                },
            )
        )
        self.log_service.add_log(
            agent="text_agent", action="text_chat", input_summary=message,
            status="success", duration_ms=self._ms(t0), run_id=trace["trace_id"],
            step="refine_text", tool_called="huggingface_generate_text",
            thought=done.thought,
            observation=done.observation,
            output_summary=f"{len(generated_text)} chars, {len(result.get('hashtags', []))} hashtags",
        )
        return {
            "chat_id": chat["id"],
            "assistant_message": reply,
            "generated_artifacts": {"text": result},
            "trace_id": trace["trace_id"],
        }

    def image_agent_chat(
        self,
        message: str,
        post_id: str,
        strength: float = 0.65,
    ) -> dict[str, Any]:
        """Regenerate the post image from the user message and current post image."""
        t0 = datetime.utcnow()
        post = self._require_post(post_id)
        chat = self.chat_service.get_or_create_chat(post_id, agent="image_agent")
        self.chat_service.add_message(chat, role="USER", content=message)

        preview = post.get("preview") or {}
        image_agent = ImageAgent(self._hf(), self.trace_service)
        current_image = image_agent.image_storage.read_post_image(post_id)
        if not current_image:
            # Fallback: filename from preview metadata if stem differs.
            current_image = image_agent.image_storage.read_bytes(preview.get("image_filename"))

        trace = self.trace_service.create_trace(
            chat_id=chat["id"],
            metadata={
                "entrypoint": "image_agent_chat",
                "post_id": post_id,
                "has_current_image": bool(current_image),
            },
        )
        task = build_image_refine_task(
            message,
            preview.get("image_prompt_optional"),
            preview.get("generated_text"),
        )
        tool_called = (
            "huggingface_image_to_image" if current_image else "huggingface_text_to_image"
        )

        try:
            result = image_agent.generate_image(
                task=task,
                trace=trace,
                platform=post.get("platform"),
                visual_style=post.get("image_style"),
                context={
                    "text_context": post.get("text_context"),
                    "text_length": post.get("text_length"),
                    "image_context": post.get("image_context"),
                    "image_style": post.get("image_style"),
                    "topic": post.get("topic"),
                },
                post_id=post_id,
                current_image=current_image,
                strength=strength,
                post_repository=self.post_repository,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            fail = compose(
                TaoEvent(
                    phase="direct_error",
                    node="ImageAgent",
                    agent="ImageAgent",
                    status="error",
                    facts={"artifact_type": "Bild", "error": error},
                )
            )
            self.log_service.add_log(
                agent="image_agent", action="image_chat", input_summary=message,
                status="error", duration_ms=self._ms(t0), run_id=trace["trace_id"],
                step="refine_image", tool_called=tool_called,
                thought=fail.thought,
                observation=fail.observation,
                output_summary=error,
            )
            raise self._to_http_error(exc) from exc

        image_ready = bool(result.get("image_url"))
        if post:
            patch: dict[str, Any] = {"image_prompt_optional": result.get("image_prompt")}
            if image_ready:
                patch["image_url"] = result["image_url"]
                patch["image_filename"] = result.get("image_filename")
            self.post_repository.merge_preview(post_id, patch)

        if image_ready:
            used_cur = bool(result.get("used_current_image"))
            if used_cur:
                fallback = (
                    "Ich habe das aktuelle Post-Bild weiterentwickelt und ein neues Bild generiert."
                )
                situation = (
                    "Image regenerated successfully by refining the current post image."
                )
            else:
                fallback = messages.IMAGE_REFINED
                situation = "Image regenerated successfully via text-to-image."
            ack = compose_specialist_reply(
                role="image",
                hf=self._hf(),
                fallback=fallback,
                situation=situation,
                user_message=message,
                post=post,
                artifact_summary=(
                    f"mode={result.get('generation_mode')}; "
                    f"source={result.get('img2img_source')}; "
                    f"image_url={result.get('image_url')}"
                ),
            )
            reply = ack
        else:
            err = result.get("image_error") or "unbekannter Fehler"
            ack = compose_specialist_reply(
                role="image",
                hf=self._hf(),
                fallback=messages.IMAGE_REFINE_PROMPT_ONLY,
                situation=(
                    "Image prompt was created but image generation failed. "
                    f"Error: {err}"
                ),
                user_message=message,
                post=post,
                artifact_summary=f"image_error={err}",
            )
            reply = f"{ack}\nFehler: {err}"
        self.chat_service.add_message(chat, role="AGENT", content=reply)
        summary = (
            f"image_url={result.get('image_url')}; mode={result.get('generation_mode')}; "
            f"source={result.get('img2img_source')}; error={result.get('image_error')}"
        )
        done = compose(
            TaoEvent(
                phase="image_return",
                node="ImageAgent",
                agent="ImageAgent",
                status="success" if image_ready else "partial_success",
                facts={
                    "image_filename": result.get("image_filename"),
                    "image_url": result.get("image_url"),
                    "image_mode": result.get("generation_mode") or "text_to_image",
                    "img2img_source": result.get("img2img_source") or "none",
                    "error": result.get("image_error"),
                },
            )
        )
        self.log_service.add_log(
            agent="image_agent", action="image_chat", input_summary=message,
            status="success" if image_ready else "error", duration_ms=self._ms(t0),
            run_id=trace["trace_id"], step="refine_image", tool_called=tool_called,
            thought=done.thought,
            observation=done.observation,
            output_summary=summary,
        )
        return {
            "chat_id": chat["id"],
            "assistant_message": reply,
            "generated_artifacts": {"image": result},
            "trace_id": trace["trace_id"],
        }

    def _ms(self, start: datetime) -> int:
        return int((datetime.utcnow() - start).total_seconds() * 1000)
