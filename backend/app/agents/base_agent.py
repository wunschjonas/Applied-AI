from __future__ import annotations

from typing import Any

from app.graphs.dependencies import record_trace_event
from app.graphs.support.tao_composer import TaoEvent
from app.services.huggingface_service import HuggingFaceService
from app.services.trace_service import TraceService


class BaseAgent:
    name = "BaseAgent"

    def __init__(self, hf: HuggingFaceService, trace_service: TraceService):
        self.hf = hf
        self.trace_service = trace_service

    def record(
        self,
        trace: dict,
        phase: str,
        status: str = "success",
        intent: str | None = None,
        **facts: Any,
    ) -> None:
        record_trace_event(
            self.trace_service,
            trace,
            TaoEvent(
                phase=phase,
                node=self.name,
                agent=self.name,
                status=status,
                intent=intent,
                facts=facts,
            ),
        )
