from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from app.agents.manager_agent import ManagerIntentClassifier
from app.graphs.state import ManagerChatState
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

    def step(
        self,
        state: ManagerChatState,
        agent: str,
        thought: str,
        action: str,
        observation: str,
        status_value: str = "success",
    ) -> None:
        step = self.deps.trace_service.add_step(state["trace"], agent, thought, action, observation, status_value)
        state["trace_steps"].append(step)

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
    ) -> None:
        self.deps.log_service.add_log(
            agent=agent,
            action=action,
            input_summary=state["user_message"][:300],
            status=status,
            duration_ms=self.elapsed_ms(started_at) if started_at else 0,
            run_id=state.get("trace_id"),
            step=step,
            tool_called=tool_called,
            thought=thought,
            observation=observation,
            output_summary=output_summary,
        )

    @staticmethod
    def elapsed_ms(start: datetime) -> int:
        return int((datetime.utcnow() - start).total_seconds() * 1000)
