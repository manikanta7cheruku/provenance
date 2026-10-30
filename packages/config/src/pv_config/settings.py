"""Application settings.

Design rules (see docs/operations/production-operations.md):
- Required values have no default, so a missing value stops startup.
- Secrets are SecretStr so they never appear in logs or repr().
- The application must not connect as the database owner, so Row Level Security
  cannot be bypassed by accident.
- Production refuses placeholder or weak values and refuses to start without a mail transport.
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


def _origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


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

    # Authentication and sessions
    signup_mode: Literal["invite", "open"] = "invite"
    email_verification_required: bool = False
    session_idle_days: int = 7
    session_max_days: int = 30

    # Where the web app is served. Used for links in emails and for the Origin check.
    public_base_url: str = "http://localhost:5173"

    # Mail transport. Empty smtp_host means "log emails" (development and tests only).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_starttls: bool = True
    mail_from: str = "Provenance <no-reply@localhost>"
    # Shown to developers when mail goes to the local inbox (Mailpit).
    dev_inbox_url: str = "http://localhost:8025"

    # Background worker (checkpoint 1.4)
    worker_poll_interval_seconds: float = 1.0
    # Visibility timeout: how long a claimed task stays hidden before another worker may take it.
    worker_lease_seconds: int = 120
    worker_heartbeat_seconds: int = 10
    task_retention_days: int = 7

    # Private file storage (resumes). A directory today; an S3-compatible bucket in checkpoint 3.7.
    file_storage_dir: str = "./storage"

    # AI provider (checkpoint 1.4 adds the plumbing; resume parsing is the first feature, 1.6).
    # Model names and prices are configuration, never code.
    # See docs/operations/llm-provider-gemini.md.
    gemini_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_embedding_model: str = ""
    llm_embedding_dimensions: int = 768
    llm_min_interval_seconds: float = 0.0
    llm_input_price_per_million: float = 0.0
    llm_output_price_per_million: float = 0.0
    llm_embedding_price_per_million: float = 0.0

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

    @field_validator("session_idle_days", "session_max_days")
    @classmethod
    def _check_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("session lifetimes must be at least 1 day")
        return value

    @field_validator("worker_poll_interval_seconds")
    @classmethod
    def _check_poll_interval(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("WORKER_POLL_INTERVAL_SECONDS must be greater than 0")
        return value

    @field_validator("worker_lease_seconds")
    @classmethod
    def _check_lease(cls, value: int) -> int:
        if value < 10:
            raise ValueError("WORKER_LEASE_SECONDS must be at least 10")
        return value

    @field_validator("worker_heartbeat_seconds", "task_retention_days", "llm_embedding_dimensions")
    @classmethod
    def _check_at_least_one(cls, value: int) -> int:
        if value < 1:
            raise ValueError("this value must be at least 1")
        return value

    @field_validator(
        "llm_min_interval_seconds",
        "llm_input_price_per_million",
        "llm_output_price_per_million",
        "llm_embedding_price_per_million",
    )
    @classmethod
    def _check_not_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("this value must not be negative")
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
        if self.session_idle_days > self.session_max_days:
            raise ValueError("SESSION_IDLE_DAYS must not exceed SESSION_MAX_DAYS")
        if self.worker_lease_seconds <= self.worker_heartbeat_seconds:
            raise ValueError("WORKER_LEASE_SECONDS must be greater than WORKER_HEARTBEAT_SECONDS")
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
            if not self.public_base_url.startswith("https://"):
                problems.append("PUBLIC_BASE_URL must be https:// in production")
            if not self.smtp_host:
                problems.append(
                    "SMTP_HOST is required in production "
                    "(password reset and verification need mail)"
                )
            if problems:
                raise ValueError("; ".join(problems))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_origins(self) -> list[str]:
        """Origins allowed to make state-changing browser requests."""
        origins = self.cors_origin_list
        public = _origin_of(self.public_base_url)
        return origins if public in origins else [*origins, public]

    @property
    def session_cookie_secure(self) -> bool:
        return self.environment == "production"

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix makes browsers require Secure, Path=/ and no Domain attribute.
        return "__Host-pv_session" if self.session_cookie_secure else "pv_session"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Values come from the environment and .env. The empty mapping keeps type
    # checkers from demanding the required fields as constructor arguments.
    no_overrides: dict[str, Any] = {}
    return Settings(**no_overrides)
