from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status

from app.agents.image_agent import ImageAgent
from app.agents.text_agent import TextAgent
from app.core.config import settings
from app.graphs.manager_chat_graph import ManagerChatGraph
from app.graphs.support import messages
from app.graphs.support.delegation import build_image_refine_task, build_text_refine_task
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
            raise self._to_http_error(exc) from exc

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
            self.trace_service.add_step(
                trace,
                "TextAgent",
                "Text generation failed.",
                "return_error",
                error,
                "error",
            )
            self.log_service.add_log(
                agent="text_agent",
                action="direct_generate_text",
                input_summary=task,
                status="error",
                duration_ms=self._ms(t0),
                run_id=trace["trace_id"],
                step="generate_text",
                tool_called="huggingface_generate_text",
                output_summary=error,
            )
            raise self._to_http_error(exc) from exc

        self.log_service.add_log(
            agent="text_agent",
            action="direct_generate_text",
            input_summary=task,
            status="success",
            duration_ms=self._ms(t0),
            run_id=trace["trace_id"],
            step="generate_text",
            tool_called="huggingface_generate_text",
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
            self.trace_service.add_step(
                trace,
                "ImageAgent",
                "Image prompt generation failed.",
                "return_error",
                error,
                "error",
            )
            self.log_service.add_log(
                agent="image_agent",
                action="direct_generate_image_prompt",
                input_summary=task,
                status="error",
                duration_ms=self._ms(t0),
                run_id=trace["trace_id"],
                step="generate_image_prompt",
                tool_called="huggingface_generate_text",
                output_summary=error,
            )
            raise self._to_http_error(exc) from exc

        self.log_service.add_log(
            agent="image_agent",
            action="direct_generate_image_prompt",
            input_summary=task,
            status="success",
            duration_ms=self._ms(t0),
            run_id=trace["trace_id"],
            step="generate_image_prompt",
            tool_called="huggingface_generate_text",
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
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.trace_service.add_step(
                trace,
                "ImageAgent",
                "Image generation failed.",
                "return_error",
                error,
                "error",
            )
            self.log_service.add_log(
                agent="image_agent",
                action="direct_generate_image",
                input_summary=task,
                status="error",
                duration_ms=self._ms(t0),
                run_id=trace["trace_id"],
                step="generate_image",
                tool_called="huggingface_text_to_image",
                output_summary=error,
            )
            raise self._to_http_error(exc) from exc

        self.log_service.add_log(
            agent="image_agent",
            action="direct_generate_image",
            input_summary=task,
            status="success" if result.get("image_url") else "error",
            duration_ms=self._ms(t0),
            run_id=trace["trace_id"],
            step="generate_image",
            tool_called="huggingface_text_to_image",
            output_summary=f"image_url={result.get('image_url')}; error={result.get('image_error')}",
        )
        return {**result, "trace_id": trace["trace_id"]}

    def _hf(self) -> HuggingFaceService:
        hf_token = settings.hf_token.get_secret_value() if settings.hf_token else None
        return HuggingFaceService(
            hf_token=hf_token,
            hf_model_id=settings.hf_model_id,
            hf_image_model_id=settings.hf_image_model_id,
        )

    def _to_http_error(self, exc: Exception) -> HTTPException:
        if isinstance(exc, HTTPException):
            return exc

        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {type(exc).__name__}: {exc}",
        )

    def text_agent_chat(self, message: str, post_id: str) -> dict[str, Any]:
        """Refine the stored marketing copy: regenerate it and write it back to the post preview."""
        t0 = datetime.utcnow()
        chat = self.chat_service.get_or_create_chat(post_id, agent="text_agent")
        self.chat_service.add_message(chat, role="USER", content=message)

        post = self.post_repository.get(post_id) or {}
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
                context=post.get("additional_context"),
            )
        except Exception as exc:
            self.log_service.add_log(
                agent="text_agent", action="text_chat", input_summary=message,
                status="error", duration_ms=self._ms(t0), run_id=trace["trace_id"],
                step="refine_text", tool_called="huggingface_generate_text",
                output_summary=f"{type(exc).__name__}: {exc}",
            )
            raise self._to_http_error(exc) from exc

        generated_text = result.get("generated_text", "")
        if post:
            self.post_repository.merge_preview(
                post_id,
                {"generated_text": generated_text, "hashtags": result.get("hashtags", [])},
            )

        reply = f"{messages.TEXT_REFINED}\n\n{generated_text}"
        self.chat_service.add_message(
            chat,
            role="AGENT",
            content=reply,
            metadata={"trace_id": trace["trace_id"], "artifact_type": "text"},
        )
        self.log_service.add_log(
            agent="text_agent", action="text_chat", input_summary=message,
            status="success", duration_ms=self._ms(t0), run_id=trace["trace_id"],
            step="refine_text", tool_called="huggingface_generate_text",
            output_summary=f"{len(generated_text)} chars, {len(result.get('hashtags', []))} hashtags",
        )
        return {
            "chat_id": chat["id"],
            "assistant_message": reply,
            "generated_artifacts": {"text": result},
            "trace_id": trace["trace_id"],
        }

    def image_agent_chat(self, message: str, post_id: str) -> dict[str, Any]:
        """Refine the stored motif: regenerate the image and overwrite {post_id}.png."""
        t0 = datetime.utcnow()
        chat = self.chat_service.get_or_create_chat(post_id, agent="image_agent")
        self.chat_service.add_message(chat, role="USER", content=message)

        post = self.post_repository.get(post_id) or {}
        preview = post.get("preview") or {}
        trace = self.trace_service.create_trace(
            chat_id=chat["id"],
            metadata={"entrypoint": "image_agent_chat", "post_id": post_id},
        )
        task = build_image_refine_task(
            message,
            preview.get("image_prompt_optional"),
            preview.get("generated_text"),
        )

        try:
            result = ImageAgent(self._hf(), self.trace_service).generate_image(
                task=task,
                trace=trace,
                platform=post.get("platform"),
                visual_style=None,
                context=post.get("additional_context"),
                post_id=post_id,
            )
        except Exception as exc:
            self.log_service.add_log(
                agent="image_agent", action="image_chat", input_summary=message,
                status="error", duration_ms=self._ms(t0), run_id=trace["trace_id"],
                step="refine_image", tool_called="huggingface_text_to_image",
                output_summary=f"{type(exc).__name__}: {exc}",
            )
            raise self._to_http_error(exc) from exc

        image_ready = bool(result.get("image_url"))
        if post:
            patch: dict[str, Any] = {"image_prompt_optional": result.get("image_prompt")}
            if image_ready:
                patch["image_url"] = result["image_url"]
                patch["image_filename"] = result.get("image_filename")
            self.post_repository.merge_preview(post_id, patch)

        headline = messages.IMAGE_REFINED if image_ready else messages.IMAGE_REFINE_PROMPT_ONLY
        reply = f"{headline}\n\n{result.get('image_prompt', '')}"
        self.chat_service.add_message(
            chat,
            role="AGENT",
            content=reply,
            metadata={
                "trace_id": trace["trace_id"],
                "artifact_type": "image",
                "image_url": result.get("image_url"),
                "image_filename": result.get("image_filename"),
            },
        )
        self.log_service.add_log(
            agent="image_agent", action="image_chat", input_summary=message,
            status="success" if image_ready else "error", duration_ms=self._ms(t0),
            run_id=trace["trace_id"], step="refine_image", tool_called="huggingface_text_to_image",
            output_summary=f"image_url={result.get('image_url')}; error={result.get('image_error')}",
        )
        return {
            "chat_id": chat["id"],
            "assistant_message": reply,
            "generated_artifacts": {"image": result},
            "trace_id": trace["trace_id"],
        }

    def _ms(self, start: datetime) -> int:
        return int((datetime.utcnow() - start).total_seconds() * 1000)
