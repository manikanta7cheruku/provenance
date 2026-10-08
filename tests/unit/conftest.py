from collections.abc import Callable
from typing import Any

import pytest

from pv_config import Settings

_ENV_KEYS = [
    "ENVIRONMENT",
    "DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "SECRET_KEY",
    "CORS_ORIGINS",
    "LOG_LEVEL",
]

VALID: dict[str, Any] = {
    "environment": "development",
    "database_url": "postgresql+psycopg://provenance_app:apppw@127.0.0.1:1/provenance",
    "migration_database_url": "postgresql+psycopg://provenance:ownerpw@127.0.0.1:1/provenance",
    "secret_key": "k" * 40,
}


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests must not depend on the developer's shell or .env file."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    def _make(**overrides: Any) -> Settings:
        values = {**VALID, **overrides}
        values = {k: v for k, v in values.items() if v is not None}
        return Settings(_env_file=None, **values)

    return _make
