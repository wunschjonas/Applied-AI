from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.agents.image_agent import ImageAgent
from app.agents.text_agent import TextAgent
from app.core.config import settings
from app.graphs.manager_chat_graph import ManagerChatGraph
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.log_service import LogService
from app.services.rag_service import RAGService
from app.services.trace_service import TraceService


class AgentService:
    def __init__(self):
        self.chat_service = ChatService()
        self.trace_service = TraceService()
        self.rag_service = RAGService(memory_url=settings.mcp_memory_url)
        self.log_service = LogService()

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
        run_id = str(uuid4())
        t0 = datetime.utcnow()
        chat = self.chat_service.get_or_create_chat(post_id, agent="text_agent")
        self.chat_service.add_message(chat, role="USER", content=message)
        try:
            hf = self._hf()
            reply = hf.generate(
                system_prompt=(
                    "You are a marketing copywriter assistant. "
                    "Help the user with text, posts, slogans and copy for any platform. "
                    "Be concise and practical."
                ),
                user_prompt=message,
                max_tokens=600,
            )
        except Exception as exc:
            self.log_service.add_log(
                agent="text_agent", action="text_chat", input_summary=message,
                status="error", duration_ms=self._ms(t0), run_id=run_id,
                step="text_chat", tool_called="huggingface_generate",
                output_summary=f"{type(exc).__name__}: {exc}",
            )
            raise self._to_http_error(exc) from exc
        self.chat_service.add_message(chat, role="AGENT", content=reply)
        self.log_service.add_log(
            agent="text_agent", action="text_chat", input_summary=message,
            status="success", duration_ms=self._ms(t0), run_id=run_id,
            step="text_chat", tool_called="huggingface_generate",
            output_summary=f"{len(reply)} chars generated",
        )
        return {"chat_id": chat["id"], "assistant_message": reply}

    def image_agent_chat(self, message: str, post_id: str) -> dict[str, Any]:
        run_id = str(uuid4())
        t0 = datetime.utcnow()
        chat = self.chat_service.get_or_create_chat(post_id, agent="image_agent")
        self.chat_service.add_message(chat, role="USER", content=message)
        try:
            hf = self._hf()
            reply = hf.generate(
                system_prompt=(
                    "You are an image prompt specialist for marketing visuals. "
                    "Help the user craft image generation prompts, describe visual styles, "
                    "and suggest composition ideas. Be specific and visual."
                ),
                user_prompt=message,
                max_tokens=600,
            )
        except Exception as exc:
            self.log_service.add_log(
                agent="image_agent", action="image_chat", input_summary=message,
                status="error", duration_ms=self._ms(t0), run_id=run_id,
                step="image_chat", tool_called="huggingface_generate",
                output_summary=f"{type(exc).__name__}: {exc}",
            )
            raise self._to_http_error(exc) from exc
        self.chat_service.add_message(chat, role="AGENT", content=reply)
        self.log_service.add_log(
            agent="image_agent", action="image_chat", input_summary=message,
            status="success", duration_ms=self._ms(t0), run_id=run_id,
            step="image_chat", tool_called="huggingface_generate",
            output_summary=f"{len(reply)} chars generated",
        )
        return {"chat_id": chat["id"], "assistant_message": reply}

    def _ms(self, start: datetime) -> int:
        return int((datetime.utcnow() - start).total_seconds() * 1000)
