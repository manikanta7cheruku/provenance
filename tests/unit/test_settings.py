from collections.abc import Callable

import pytest
from pydantic import ValidationError

from pv_config import Settings

Make = Callable[..., Settings]


def test_valid_development_settings(make_settings: Make) -> None:
    assert make_settings().environment == "development"


def test_missing_secret_key_fails_fast(make_settings: Make) -> None:
    with pytest.raises(ValidationError):
        make_settings(secret_key=None)


def test_missing_environment_fails_fast(make_settings: Make) -> None:
    with pytest.raises(ValidationError):
        make_settings(environment=None)


def test_short_secret_key_rejected(make_settings: Make) -> None:
    with pytest.raises(ValidationError):
        make_settings(secret_key="short")


def test_wrong_database_scheme_rejected(make_settings: Make) -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url="postgres://u:p@localhost/db")


def test_app_must_not_connect_as_owner(make_settings: Make) -> None:
    same = "postgresql+psycopg://provenance:pw@localhost:5433/provenance"
    with pytest.raises(ValidationError, match="different roles"):
        make_settings(database_url=same, migration_database_url=same)


def test_production_rejects_placeholder_secret(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        make_settings(environment="production", secret_key="change-me-" + "x" * 40)


def test_production_rejects_http_origins(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="https"):
        make_settings(environment="production", cors_origins="http://example.com")


def test_production_accepts_strong_configuration(make_settings: Make) -> None:
    settings = make_settings(environment="production", cors_origins="https://app.example.com")
    assert settings.cors_origin_list == ["https://app.example.com"]


def test_secrets_never_appear_in_repr(make_settings: Make) -> None:
    text = repr(make_settings())
    assert "k" * 40 not in text
    assert "apppw" not in text
    assert "ownerpw" not in text
