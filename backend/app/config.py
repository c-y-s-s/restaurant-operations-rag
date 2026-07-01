from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "Restaurant Operations RAG"
    environment: str = "development"
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-5.4-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    database_url: str = ""
    admin_secret: str = "change-me"
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    max_daily_requests_per_ip: int = 40
    retrieval_min_semantic_score: float = 0.28
    retrieval_candidates: int = 8
    generation_context_chunks: int = 5

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_configured(self) -> bool:
        return bool(
            self.openai_api_key
            and self.database_url
            and "example.supabase.co" not in self.database_url
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
