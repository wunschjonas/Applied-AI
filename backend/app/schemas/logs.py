from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentLogEntry(BaseModel):
    id: str
    run_id: str
    agent: Literal["text_agent", "image_agent", "manager_agent"]
    timestamp: datetime
    step: str
    tool_called: str | None = None
    decision: str | None = None
    action: str
    input_summary: str = Field(max_length=300)
    output_summary: str | None = Field(default=None, max_length=300)
    status: Literal["success", "error", "skipped"]
    duration_ms: int


class AgentLogsResponse(BaseModel):
    agent: str
    total: int
    logs: list[AgentLogEntry]
