from __future__ import annotations

from app.services.huggingface_service import HuggingFaceService
from app.services.trace_service import TraceService


class BaseAgent:
    name = "BaseAgent"

    def __init__(self, hf: HuggingFaceService, trace_service: TraceService):
        self.hf = hf
        self.trace_service = trace_service

    def trace(
        self,
        trace: dict,
        thought: str,
        action: str,
        observation: str,
        status_value: str = "success",
    ) -> None:
        self.trace_service.add_step(
            trace=trace,
            agent=self.name,
            thought=thought,
            action=action,
            observation=observation,
            status_value=status_value,
        )
