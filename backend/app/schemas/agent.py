from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.chat import _strip_nonempty


class TextGenerateRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    platform: str | None = "linkedin"
    tone: str | None = "professional"
    target_audience: str | None = None
    context: str | dict[str, Any] | None = None

    @field_validator("task", mode="before")
    @classmethod
    def strip_task(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_nonempty(value)
        return value


class TextGenerateResponse(BaseModel):
    generated_text: str
    hashtags: list[str] = Field(default_factory=list)
    trace_id: str


class ImagePromptRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    platform: str | None = None
    visual_style: str | None = None
    context: str | dict[str, Any] | None = None
    post_id: str | None = None

    @field_validator("task", mode="before")
    @classmethod
    def strip_task(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_nonempty(value)
        return value


class ImagePromptResponse(BaseModel):
    image_prompt: str
    negative_prompt_optional: str | None = None
    suggested_style: str | None = None
    trace_id: str


class ImageGenerateResponse(ImagePromptResponse):
    image_url: str | None = None
    image_filename: str | None = None
    image_content_type: str | None = None
    image_error: str | None = None
