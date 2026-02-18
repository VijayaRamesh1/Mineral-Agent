"""
Configuration loader for the Critical Minerals Signal Hunter.

Loads settings from environment variables (via .env) and watchlist.yaml.
Uses pydantic-settings for type-safe config with validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — all values loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Gemini
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")

    # LangSmith
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(
        default="critical-minerals-agent", alias="LANGCHAIN_PROJECT"
    )
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com", alias="LANGCHAIN_ENDPOINT"
    )

    # Database
    database_url: str = Field(default="sqlite:///./data/signals.db", alias="DATABASE_URL")

    # Pipeline
    watchlist_path: Path = Field(default=Path("watchlist.yaml"), alias="WATCHLIST_PATH")
    edgar_rate_limit_rps: int = Field(default=10, alias="EDGAR_RATE_LIMIT_RPS")
    price_lookback_days: int = Field(default=30, alias="PRICE_LOOKBACK_DAYS")
    news_lookback_hours: int = Field(default=48, alias="NEWS_LOOKBACK_HOURS")
    max_filings_per_ticker: int = Field(default=5, alias="MAX_FILINGS_PER_TICKER")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    gemini_temperature: float = Field(default=0.0, alias="GEMINI_TEMPERATURE")
    gemini_max_tokens: int = Field(default=1024, alias="GEMINI_MAX_TOKENS")

    # FastAPI
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Scheduler
    pipeline_cron_hour: int = Field(default=6, alias="PIPELINE_CRON_HOUR")
    pipeline_cron_minute: int = Field(default=0, alias="PIPELINE_CRON_MINUTE")

    # Telegram (optional)
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_channel_id: str = Field(default="", alias="TELEGRAM_CHANNEL_ID")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )


# Module-level singleton
settings = Settings()
