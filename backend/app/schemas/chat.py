from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def _strip_nonempty(value: str, *, max_length: int = 4000) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be empty or whitespace-only")
    if len(cleaned) > max_length:
        raise ValueError(f"must be at most {max_length} characters")
    return cleaned


class ChatMessage(BaseModel):
    role: Literal["USER", "AGENT"]
    content: str


class ManagerChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    post_id: str = Field(min_length=1)
    context: str | dict[str, Any] | None = None

    @field_validator("message", "post_id", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_nonempty(value)
        return value


class ManagerChatResponse(BaseModel):
    chat_id: str
    assistant_message: str
    used_agents: list[str] = Field(default_factory=list)
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    post_updates: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    generation_pending: bool = False


class ManagerGenerateRequest(BaseModel):
    post_id: str = Field(min_length=1)

    @field_validator("post_id", mode="before")
    @classmethod
    def strip_post_id(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_nonempty(value)
        return value


class TextAgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    post_id: str = Field(min_length=1)

    @field_validator("message", "post_id", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_nonempty(value)
        return value


class TextAgentChatResponse(BaseModel):
    chat_id: str
    assistant_message: str
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class ImageAgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    post_id: str = Field(min_length=1)

    @field_validator("message", "post_id", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_nonempty(value)
        return value


class ImageAgentChatResponse(BaseModel):
    chat_id: str
    assistant_message: str
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class ChatHistoryResponse(BaseModel):
    id: str
    agent: str
    messages: list[ChatMessage] = Field(default_factory=list)
