import os
from functools import lru_cache
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    app_name: str = Field(default="AI Coach")
    database_url: str = Field(default="sqlite:///./db.sqlite")
    openai_api_key: str | None = Field(default=None, env="OPENAI_API_KEY")
    use_ai: bool = Field(default=True, env="USE_AI_SELECTOR")
    timezone: str = Field(default=os.getenv("TZ", "UTC"))
    task_sample_days: int = Field(default=14)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
