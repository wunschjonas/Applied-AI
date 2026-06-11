from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.agents.image_agent import ImageAgent
from app.agents.text_agent import TextAgent
from app.core.config import settings
from app.graphs.manager_chat_graph import ManagerChatGraph
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.rag_service import RAGService
from app.services.trace_service import TraceService


class AgentService:
    def __init__(self):
        self.chat_service = ChatService()
        self.trace_service = TraceService()
        self.rag_service = RAGService()

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
            self.trace_service.add_step(
                trace,
                "TextAgent",
                "Text generation failed.",
                "return_error",
                f"{type(exc).__name__}: {exc}",
                "error",
            )
            raise self._to_http_error(exc) from exc

        return {**result, "trace_id": trace["trace_id"]}

    def generate_image_prompt(
        self,
        task: str,
        platform: str | None,
        visual_style: str | None,
        context: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        trace = self.trace_service.create_trace(metadata={"entrypoint": "direct_image_agent"})
        try:
            result = ImageAgent(self._hf(), self.trace_service).generate_prompt(
                task=task,
                trace=trace,
                platform=platform,
                visual_style=visual_style,
                context=context,
            )
        except Exception as exc:
            self.trace_service.add_step(
                trace,
                "ImageAgent",
                "Image prompt generation failed.",
                "return_error",
                f"{type(exc).__name__}: {exc}",
                "error",
            )
            raise self._to_http_error(exc) from exc

        return {**result, "trace_id": trace["trace_id"]}

    def _hf(self) -> HuggingFaceService:
        hf_token = settings.hf_token.get_secret_value() if settings.hf_token else None
        return HuggingFaceService(hf_token=hf_token, hf_model_id=settings.hf_model_id)

    def _to_http_error(self, exc: Exception) -> HTTPException:
        if isinstance(exc, HTTPException):
            return exc

        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {type(exc).__name__}: {exc}",
        )

    def text_agent_chat(self, message: str, post_id: str) -> dict[str, Any]:
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
            raise self._to_http_error(exc) from exc
        self.chat_service.add_message(chat, role="AGENT", content=reply)
        return {"chat_id": chat["id"], "assistant_message": reply}

    def image_agent_chat(self, message: str, post_id: str) -> dict[str, Any]:
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
            raise self._to_http_error(exc) from exc
        self.chat_service.add_message(chat, role="AGENT", content=reply)
        return {"chat_id": chat["id"], "assistant_message": reply}
