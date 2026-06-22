from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "OrbitOps AI"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_secret_key: str = Field(min_length=32)
    database_url: str = "sqlite+aiosqlite:///./orbitops.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str | None = Field(default=None, min_length=12)
    llm_default_provider: Literal["mock", "openai", "anthropic", "google"] = "mock"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    live_llm_enabled: bool = False
    openai_model: str = "gpt-4.1-mini"
    anthropic_model: str = "claude-sonnet-4-20250514"
    google_model: str = "gemini-2.5-flash"
    llm_timeout_seconds: int = 45
    openai_input_cost_per_million: float = 0
    openai_output_cost_per_million: float = 0
    anthropic_input_cost_per_million: float = 0
    anthropic_output_cost_per_million: float = 0
    google_input_cost_per_million: float = 0
    google_output_cost_per_million: float = 0
    delivery_enabled: bool = False
    email_webhook_secret: str | None = Field(default=None, min_length=24)
    whatsapp_webhook_secret: str | None = Field(default=None, min_length=24)
    webhook_tolerance_seconds: int = 300
    message_max_attempts: int = 3
    langsmith_tracing: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",")]
        return value

    @model_validator(mode="after")
    def validate_environment_security(self):
        if self.app_env in {"development", "test"} and not self.bootstrap_admin_password:
            raise ValueError("BOOTSTRAP_ADMIN_PASSWORD is required in development and test")
        if self.app_env in {"staging", "production"}:
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is not allowed in staging or production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS is not allowed in staging or production")
            if self.delivery_enabled and (
                not self.email_webhook_secret or not self.whatsapp_webhook_secret
            ):
                raise ValueError("Webhook secrets are required when delivery is enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
