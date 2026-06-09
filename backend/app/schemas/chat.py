from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, constr


class ChatMessage(BaseModel):
    role: Literal["USER", "AGENT"]
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


class TextAgentChatRequest(BaseModel):
    message: constr(min_length=1, max_length=4000)
    chat_id: str | None = None


class TextAgentChatResponse(BaseModel):
    chat_id: str
    assistant_message: str


class ImageAgentChatRequest(BaseModel):
    message: constr(min_length=1, max_length=4000)
    chat_id: str | None = None


class ImageAgentChatResponse(BaseModel):
    chat_id: str
    assistant_message: str


class ChatHistoryResponse(BaseModel):
    chat_id: str
    agent: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage] = Field(default_factory=list)
