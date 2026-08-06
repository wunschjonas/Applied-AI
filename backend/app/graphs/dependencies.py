from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from app.agents.manager_agent import ManagerIntentClassifier
from app.graphs.state import ManagerChatState
from app.graphs.support.tao_composer import TaoEvent, TaoTriple, compose
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.image_storage_service import ImageStorageService
from app.services.log_service import LogService
from app.services.post_repository import PostRepository
from app.services.rag_service import RAGService
from app.services.trace_service import TraceService


@dataclass
class GraphDependencies:
    chat_service: ChatService
    trace_service: TraceService
    rag_service: RAGService
    hf_factory: Callable[[], HuggingFaceService]
    log_service: LogService
    image_storage: ImageStorageService
    intent_classifier: ManagerIntentClassifier
    post_repository: PostRepository


class StepRecorder:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps

    def record(
        self,
        state: ManagerChatState,
        event: TaoEvent,
    ) -> TaoTriple:
        """Compose TAO text from workflow facts and append a trace step."""
        triple = compose(event)
        agent = event.agent or event.node
        step = self.deps.trace_service.add_step(
            state["trace"],
            agent,
            triple.thought,
            triple.action,
            triple.observation,
            event.status,
        )
        state["trace_steps"].append(step)
        return triple

    def log(
        self,
        state: ManagerChatState,
        agent: str,
        status: str,
        step: str,
        started_at: datetime | None = None,
        action: str = "manager_chat",
        tool_called: str | None = None,
        thought: str | None = None,
        observation: str | None = None,
        output_summary: str | None = None,
        event: TaoEvent | None = None,
    ) -> None:
        if event is not None:
            triple = compose(event)
            thought = triple.thought
            observation = triple.observation
            if action == "manager_chat":
                action = triple.action
        self.deps.log_service.add_log(
            agent=agent,
            action=action,
            input_summary=state["user_message"][:500],
            status=status,
            duration_ms=self.elapsed_ms(started_at) if started_at else 0,
            run_id=state.get("trace_id"),
            step=step,
            tool_called=tool_called,
            thought=thought,
            observation=observation,
            output_summary=output_summary,
            post_id=state.get("post_id"),
        )

    @staticmethod
    def elapsed_ms(start: datetime) -> int:
        return int((datetime.utcnow() - start).total_seconds() * 1000)


def record_trace_event(
    trace_service: TraceService,
    trace: dict[str, Any],
    event: TaoEvent,
) -> TaoTriple:
    """Record a composed TAO step outside the LangGraph StepRecorder (direct agents)."""
    triple = compose(event)
    agent = event.agent or event.node
    trace_service.add_step(
        trace,
        agent,
        triple.thought,
        triple.action,
        triple.observation,
        event.status,
    )
    return triple
