"""
Application configuration using Pydantic Settings.
Loads environment variables from a .env file.
"""
from pydantic_settings import SettingsConfigDict
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App Settings
    app_name: str = Field(default="Smart Personal Planner", alias="APP_NAME")
    debug: bool = Field(default=True, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default="change-this-secret-key", alias="SECRET_KEY")

    # Database
    database_url: str = Field(alias="DATABASE_URL")

    # Telegram
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_url: Optional[str] = Field(default=None, alias="TELEGRAM_WEBHOOK_URL")

    # Google Gemini
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    google_model: str = Field(default="gemini-pro", alias="GOOGLE_MODEL")

    # Perplexity (Fallback LLM)
    perplexity_api_key: Optional[str] = Field(default=None, alias="PERPLEXITY_API_KEY")
    perplexity_model: str = Field(default="llama-3.1-sonar-small-128k-online", alias="PERPLEXITY_MODEL")

    # Pinecone
    pinecone_api_key: Optional[str] = Field(default=None, alias="PINECONE_API_KEY")
    pinecone_environment: Optional[str] = Field(default=None, alias="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field(default="smart-planner", alias="PINECONE_INDEX_NAME")

    # Redis (Optional)
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Rate Limiting
    llm_rate_limit_calls: int = Field(default=100, alias="LLM_RATE_LIMIT_CALLS")
    llm_rate_limit_period: int = Field(default=3600, alias="LLM_RATE_LIMIT_PERIOD")

    # Agent Settings
    max_retry_attempts: int = Field(default=3, alias="MAX_RETRY_ATTEMPTS")
    agent_timeout_seconds: int = Field(default=30, alias="AGENT_TIMEOUT_SECONDS")

    # Notification Settings
    enable_motivational_messages: bool = Field(default=True, alias="ENABLE_MOTIVATIONAL_MESSAGES")
    enable_birthday_reminders: bool = Field(default=True, alias="ENABLE_BIRTHDAY_REMINDERS")
    enable_festival_greetings: bool = Field(default=True, alias="ENABLE_FESTIVAL_GREETINGS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Convenience export
settings = get_settings()
