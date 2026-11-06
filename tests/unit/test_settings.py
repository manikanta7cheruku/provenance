from collections.abc import Callable

import pytest
from pydantic import ValidationError

from pv_config import Settings

Make = Callable[..., Settings]

PROD = {
    "environment": "production",
    "cors_origins": "https://app.example.com",
    "public_base_url": "https://app.example.com",
    "smtp_host": "smtp.example.com",
    "token_encryption_keys": "t" * 40,
}


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
        make_settings(**{**PROD, "secret_key": "change-me-" + "x" * 40})


def test_production_rejects_http_origins(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="https"):
        make_settings(**{**PROD, "cors_origins": "http://example.com"})


def test_production_accepts_strong_configuration(make_settings: Make) -> None:
    settings = make_settings(**PROD)
    assert settings.cors_origin_list == ["https://app.example.com"]
    assert settings.session_cookie_secure is True
    assert settings.session_cookie_name == "__Host-pv_session"


def test_production_requires_mail_transport(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="SMTP_HOST"):
        make_settings(**{**PROD, "smtp_host": ""})


def test_production_requires_https_public_url(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="PUBLIC_BASE_URL"):
        make_settings(**{**PROD, "public_base_url": "http://app.example.com"})


def test_development_cookie_is_not_secure_and_has_plain_name(make_settings: Make) -> None:
    settings = make_settings()
    assert settings.session_cookie_secure is False
    assert settings.session_cookie_name == "pv_session"


def test_idle_lifetime_cannot_exceed_maximum(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="SESSION_IDLE_DAYS"):
        make_settings(session_idle_days=40, session_max_days=30)


def test_allowed_origins_include_the_public_url(make_settings: Make) -> None:
    settings = make_settings(
        cors_origins="http://localhost:3000", public_base_url="http://localhost:5173"
    )
    assert settings.allowed_origins == ["http://localhost:3000", "http://localhost:5173"]


def test_secrets_never_appear_in_repr(make_settings: Make) -> None:
    text = repr(make_settings())
    assert "k" * 40 not in text
    assert "apppw" not in text
    assert "ownerpw" not in text


def test_production_requires_token_encryption_keys(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="TOKEN_ENCRYPTION_KEYS"):
        make_settings(**{**PROD, "token_encryption_keys": ""})


def test_production_rejects_a_placeholder_token_key(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="TOKEN_ENCRYPTION_KEYS"):
        make_settings(**{**PROD, "token_encryption_keys": "change-me-" + "x" * 30})


def test_a_token_key_must_be_long_and_not_repeated(make_settings: Make) -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        make_settings(token_encryption_keys="short")
    key = "a" * 40
    with pytest.raises(ValidationError, match="twice"):
        make_settings(token_encryption_keys=f"{key},{key}")
    assert make_settings(
        token_encryption_keys=f"{key}, {'b' * 40}"
    ).token_encryption_keys.get_secret_value()


def test_development_does_not_need_token_encryption_keys(make_settings: Make) -> None:
    assert make_settings().token_encryption_keys.get_secret_value() == ""
