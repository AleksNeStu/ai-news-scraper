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

    # SMTP (Task #8 / ADR-012 §12.6) — outbound email transport.
    # When ``smtp_host`` is unset the email worker logs and bails,
    # leaving the digest ``delivery_status = "notified"`` (in-app only).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # AI Brief (Task #8 / ADR-012 §12.11) — kill switches for the cron
    # + router mount. ``digest_enabled`` is the primary setting;
    # ``BRIEF_DISABLED=1`` env is a back-compat alias.
    digest_enabled: bool = True
    brief_disabled: bool = False

    # RFC 8058 unsubscribe JWT secret (HS256). MUST be set in production;
    # the unsubscribe endpoint refuses to mint tokens otherwise.
    unsubscribe_jwt_secret: str = ""

    @property
    def effective_digest_enabled(self) -> bool:
        """True iff the brief subsystem is allowed to start.

        Both ``DIGEST_ENABLED=true`` AND ``BRIEF_DISABLED`` unset are
        required. Used by lifespan to gate the cron AND the router mount.
        """
        return self.digest_enabled and not self.brief_disabled

    @property
    def openai_key_usable(self) -> bool:
        """True iff ``OPENAI_API_KEY`` looks real (not the placeholder)."""
        return self.openai_api_key not in ("", "sk-replace-me", None)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
