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
    thought: str | None = None
    action: str
    observation: str | None = None
    input_summary: str = Field(max_length=500)
    output_summary: str | None = Field(default=None, max_length=2000)
    status: Literal["success", "error", "skipped", "needs_input"]
    duration_ms: int
    post_id: str | None = None


class AgentLogsResponse(BaseModel):
    agent: str
    total: int
    logs: list[AgentLogEntry]


class AgentLogsDeleteResponse(BaseModel):
    deleted: int
    scope: Literal["all", "post"]
    post_id: str | None = None
