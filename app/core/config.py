"""
Core application configuration.

Loads all settings from environment variables via python-dotenv.
No secrets are hardcoded anywhere in this module.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── LLM Provider ─────────────────────────────────────────────────────────
    OPENAI_API_KEY: str
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    MODEL_NAME: str = "gpt-4o-mini"

    # ── App Meta ──────────────────────────────────────────────────────────────
    APP_NAME: str = "TalentScout"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── CORS / Security ───────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["*"]
    SECRET_KEY: str = "change-me-in-production"

    # ── LLM Params ────────────────────────────────────────────────────────────
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 1024
    LLM_TIMEOUT: int = 30  # seconds

    # ── Bonus Hooks ───────────────────────────────────────────────────────────
    ENABLE_SENTIMENT_ANALYSIS: bool = False
    DEFAULT_LANGUAGE: str = "en"
    ENABLE_AUTH: bool = False


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()


settings = get_settings()
