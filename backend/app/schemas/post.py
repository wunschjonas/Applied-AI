from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, constr


class Platform(str, Enum):
    linkedin = "linkedin"
    instagram = "instagram"
    x = "x"
    blog = "blog"
    tiktok = "tiktok"
    facebook = "facebook"


class PostStatus(str, Enum):
    draft = "draft"
    processing = "processing"
    preview_ready = "preview_ready"
    error = "error"


class PostInit(BaseModel):
    title: constr(min_length=3, max_length=200)


class PostInitResponse(BaseModel):
    post_id: str
    title: str
    welcome_message: str | None = None
    missing_fields: list[str] = Field(default_factory=list)


class PostCreate(BaseModel):
    title: constr(min_length=3, max_length=200)
    topic: constr(min_length=3, max_length=200)
    platform: Platform
    target_audience: constr(min_length=3, max_length=300)
    tone_of_voice: constr(min_length=3, max_length=120)
    additional_context: str | None = Field(default=None, max_length=1000)


class PostUpdate(BaseModel):
    title: constr(min_length=3, max_length=200) | None = None
    topic: constr(min_length=3, max_length=200) | None = None
    platform: Platform | None = None
    target_audience: constr(min_length=3, max_length=300) | None = None
    tone_of_voice: constr(min_length=3, max_length=120) | None = None
    additional_context: str | None = Field(default=None, max_length=1000)


class PostPreview(BaseModel):
    generated_text: str = ""
    post_structure: dict[str, Any] = Field(default_factory=dict)
    hashtags: list[str] = Field(default_factory=list)
    image_prompt_optional: str | None = None
    image_url: str | None = None
    image_filename: str | None = None


class PostResponse(BaseModel):
    id: str
    title: str
    status: PostStatus
    topic: str | None = None
    platform: Platform | None = None
    target_audience: str | None = None
    tone_of_voice: str | None = None
    additional_context: str | None = None
    preview: PostPreview | None = None
    missing_fields: list[str] = Field(default_factory=list)
