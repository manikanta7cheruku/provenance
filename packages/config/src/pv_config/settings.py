"""Application settings.

Design rules (see docs/operations/production-operations.md):
- Required values have no default, so a missing value stops startup.
- Secrets are SecretStr so they never appear in logs or repr().
- The application must not connect as the database owner, so Row Level Security
  (checkpoint 1.2) cannot be bypassed by accident.
- Production refuses placeholder or weak values.
"""

from functools import lru_cache
from typing import Any, Literal, Self
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DB_SCHEME = "postgresql+psycopg://"
_MIN_SECRET_LENGTH = 32
_PLACEHOLDER = "change-me"


def _db_user(url: str) -> str:
    return urlsplit(url).username or ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"]
    database_url: SecretStr
    migration_database_url: SecretStr
    secret_key: SecretStr
    cors_origins: str = ""
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _check_scheme(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(_DB_SCHEME):
            raise ValueError(f"database URL must start with {_DB_SCHEME}")
        return value

    @field_validator("secret_key")
    @classmethod
    def _check_secret_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < _MIN_SECRET_LENGTH:
            raise ValueError(f"SECRET_KEY must be at least {_MIN_SECRET_LENGTH} characters")
        return value

    @model_validator(mode="after")
    def _check_cross_field_rules(self) -> Self:
        app_user = _db_user(self.database_url.get_secret_value())
        owner_user = _db_user(self.migration_database_url.get_secret_value())
        if app_user == owner_user:
            raise ValueError(
                "DATABASE_URL and MIGRATION_DATABASE_URL must use different roles. "
                "The application must not connect as the database owner."
            )
        if self.environment == "production":
            problems: list[str] = []
            for name, secret in (
                ("SECRET_KEY", self.secret_key),
                ("DATABASE_URL", self.database_url),
                ("MIGRATION_DATABASE_URL", self.migration_database_url),
            ):
                if _PLACEHOLDER in secret.get_secret_value():
                    problems.append(f"{name} still contains a placeholder value")
            if any(not origin.startswith("https://") for origin in self.cors_origin_list):
                problems.append("CORS_ORIGINS must all be https:// in production")
            if problems:
                raise ValueError("; ".join(problems))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Values come from the environment and .env. The empty mapping keeps type
    # checkers from demanding the required fields as constructor arguments.
    no_overrides: dict[str, Any] = {}
    return Settings(**no_overrides)
