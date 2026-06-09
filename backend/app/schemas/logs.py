from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentLogEntry(BaseModel):
    id: str
    agent: Literal["text_agent", "image_agent", "manager_agent"]
    timestamp: datetime
    action: str
    input_summary: str = Field(max_length=200)
    status: Literal["success", "error"]
    duration_ms: int


class AgentLogsResponse(BaseModel):
    agent: str
    total: int
    logs: list[AgentLogEntry]
