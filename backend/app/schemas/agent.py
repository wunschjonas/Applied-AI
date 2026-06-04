from typing import Any

from pydantic import BaseModel, Field, constr


class TextGenerateRequest(BaseModel):
    task: constr(min_length=1, max_length=4000)
    platform: str | None = "linkedin"
    tone: str | None = "professional"
    target_audience: str | None = None
    context: str | dict[str, Any] | None = None


class TextGenerateResponse(BaseModel):
    generated_text: str
    hashtags: list[str] = Field(default_factory=list)
    trace_id: str


class ImagePromptRequest(BaseModel):
    task: constr(min_length=1, max_length=4000)
    platform: str | None = None
    visual_style: str | None = None
    context: str | dict[str, Any] | None = None


class ImagePromptResponse(BaseModel):
    image_prompt: str
    negative_prompt_optional: str | None = None
    suggested_style: str | None = None
    trace_id: str
