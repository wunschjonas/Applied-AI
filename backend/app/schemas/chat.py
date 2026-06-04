from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, constr


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManagerChatRequest(BaseModel):
    message: constr(min_length=1, max_length=4000)
    chat_id: str | None = None
    context: str | dict[str, Any] | None = None


class ManagerChatResponse(BaseModel):
    chat_id: str
    assistant_message: str
    used_agents: list[str] = Field(default_factory=list)
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    trace_id: str


class ChatHistoryResponse(BaseModel):
    chat_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage] = Field(default_factory=list)
