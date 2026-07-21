"""Application configuration, sourced from the environment via pydantic-settings.

Secrets never live in code (see .env.example). Settings are validated once at
startup and injected everywhere else, so a misconfiguration fails fast. In
production we refuse to boot with the default JWT secret.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "change-me-in-production-use-a-48-byte-random-secret"


class AppEnv(StrEnum):
    LOCAL = "local"
    CI = "ci"
    PRODUCTION = "production"


class LlmMode(StrEnum):
    SANDBOX = "sandbox"
    REAL = "real"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_env: AppEnv = AppEnv.LOCAL
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_issuer: str = "campaign-studio"
    jwt_ttl_seconds: int = 3600
    service_account_id: str = "marketer"
    service_account_password: str = "local-dev-password"

    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    llm_mode: LlmMode = LlmMode.SANDBOX
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "llama3.1"
    llm_timeout_seconds: float = 60.0

    max_segments: int = 8
    max_variants_per_segment: int = 5
    max_request_bytes: int = 262_144

    # Cost guardrails (ADR-004). Process-local daily spend thresholds in USD; at the
    # cap, real-model generation degrades to the free sandbox model.
    daily_budget_warn_usd: float = 15.0
    daily_budget_cap_usd: float = 25.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        weak_secret = self.jwt_secret == _DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32
        if self.app_env is AppEnv.PRODUCTION and weak_secret:
            raise ValueError("JWT_SECRET must be a strong, non-default secret in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
