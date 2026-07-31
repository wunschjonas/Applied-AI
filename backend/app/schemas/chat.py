from typing import Any, Literal

from pydantic import BaseModel, Field, constr


class ChatMessage(BaseModel):
    role: Literal["USER", "AGENT"]
    content: str


class ManagerChatRequest(BaseModel):
    message: constr(min_length=1, max_length=4000)
    post_id: str
    context: str | dict[str, Any] | None = None


class ManagerChatResponse(BaseModel):
    chat_id: str
    assistant_message: str
    used_agents: list[str] = Field(default_factory=list)
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    post_updates: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


class TextAgentChatRequest(BaseModel):
    message: constr(min_length=1, max_length=4000)
    post_id: str


class TextAgentChatResponse(BaseModel):
    chat_id: str
    assistant_message: str
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class ImageAgentChatRequest(BaseModel):
    message: constr(min_length=1, max_length=4000)
    post_id: str


class ImageAgentChatResponse(BaseModel):
    chat_id: str
    assistant_message: str
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class ChatHistoryResponse(BaseModel):
    id: str
    agent: str
    messages: list[ChatMessage] = Field(default_factory=list)
