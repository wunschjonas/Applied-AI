from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceStep(BaseModel):
    index: int
    agent: str
    thought: str
    action: str
    observation: str
    status: str = "success"
    timestamp: datetime


class TraceResponse(BaseModel):
    trace_id: str
    chat_id: str | None = None
    created_at: datetime
    steps: list[TraceStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
