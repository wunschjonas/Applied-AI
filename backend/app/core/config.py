from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_version: str = "0.2.0"

    hf_token: SecretStr | None = Field(default=None, alias="HF_TOKEN")
    hf_model_id: str = Field(default="Qwen/Qwen2.5-7B-Instruct", alias="HF_MODEL_ID")

    data_dir: Path = Path(__file__).resolve().parent.parent / "storage" / "data"
    posts_file: Path = data_dir / "posts.json"
    chats_file: Path = data_dir / "chats.json"
    traces_file: Path = data_dir / "traces.json"
    agent_logs_file: Path = data_dir / "agent_logs.json"

    class Config:
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
