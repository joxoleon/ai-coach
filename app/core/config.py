import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        env_file_encoding="utf-8",
    )
    app_name: str = Field(default="AI Coach")
    database_url: str = Field(default="sqlite:///./db.sqlite")
    openai_api_key: str | None = Field(default=None, env="OPENAI_API_KEY")
    use_ai: bool = Field(default=True, env="USE_AI_SELECTOR")
    timezone: str = Field(default=os.getenv("TZ", "UTC"))
    task_sample_days: int = Field(default=14)
    time_budget: int = Field(default=60, description="Daily time budget in minutes")
    max_items: int = Field(default=6, description="Maximum items total per day")
    avoid_days: int = Field(default=2, description="Avoid repeating same task within N days")
    task_limits: dict = Field(
        default_factory=lambda: {
            "DSA Fundamentals": 2,
            "LeetCode": 1,
            "Leetcode": 1,
            "Habits": 3,
            "Study": 1,
        }
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
