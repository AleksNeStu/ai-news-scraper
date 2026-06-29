"""Application settings, loaded from env vars via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8082
    api_internal_url: str = "http://localhost:8082"

    # Postgres
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_news"
    )
    database_url_sync: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ai_news"
    )

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_persist_dir: str = "./chroma_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AI providers
    openai_api_key: str = "sk-replace-me"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    anthropic_api_key: str = ""
    # Multi-provider selection (ADR-011 §11.5) — defaults to deepseek
    # (cheapest direct chat path). ``openai_*`` keys above are kept
    # for backward compatibility; the active provider is selected by
    # ``LLM_PROVIDER`` and reads its key from the matching per-provider
    # field below.
    llm_provider: Literal["deepseek", "gemini", "openrouter"] = "deepseek"
    llm_model: str | None = None  # override; otherwise provider default
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    google_api_key: str = ""  # mirror, see ~/.claude/CLAUDE.md TaskMaster config
    openrouter_api_key: str = ""
    embedding_dimensions: int = 1536

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_min: int = 1440  # 24h

    # RSS
    rss_poll_interval_sec: int = 900
    rss_max_items_per_poll: int = 50
    rss_user_agent: str = "ai-news-scraper/0.1"

    # CORS
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
