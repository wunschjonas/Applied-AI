from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_version: str = "0.2.0"

    hf_token: SecretStr | None = Field(default=None, alias="HF_TOKEN")
    hf_model_id: str = Field(default="Qwen/Qwen2.5-7B-Instruct", alias="HF_MODEL_ID")
    hf_image_model_id: str = Field(default="black-forest-labs/FLUX.1-schnell", alias="HF_IMAGE_MODEL_ID")
    hf_image_to_image_model_id: str = Field(
        default="stabilityai/stable-diffusion-xl-base-1.0",
        alias="HF_IMAGE_TO_IMAGE_MODEL_ID",
    )
    hf_caption_model_id: str = Field(
        default="Salesforce/blip-image-captioning-base",
        alias="HF_CAPTION_MODEL_ID",
    )

    mcp_memory_url: str = Field(default="http://localhost:8765/mcp", alias="MCP_MEMORY_URL")
    tao_verbose: bool = Field(default=True, alias="TAO_VERBOSE")
    web_search_enabled: bool = Field(default=True, alias="WEB_SEARCH_ENABLED")

    data_dir: Path = Path(__file__).resolve().parent.parent / "storage" / "data"
    generated_images_dir: Path = Path(__file__).resolve().parent.parent / "storage" / "generated_images"
    uploads_dir: Path = Path(__file__).resolve().parent.parent / "storage" / "uploads"
    posts_file: Path = data_dir / "posts.json"
    chats_file: Path = data_dir / "chats.json"
    traces_file: Path = data_dir / "traces.json"
    agent_logs_file: Path = data_dir / "agent_logs.json"

    class Config:
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
