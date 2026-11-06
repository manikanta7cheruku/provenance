"""Checkpoint 3.7: the checks an operator runs before and after a deploy (settings and storage)."""

from collections.abc import Callable
from pathlib import Path

import pytest

from pv_api.readiness import (
    FAIL,
    OK,
    WARN,
    Check,
    run_checks,
    settings_checks,
    storage_checks,
    worst,
)
from pv_config import Settings

Make = Callable[..., Settings]

PRODUCTION = {
    "environment": "production",
    "cors_origins": "https://app.example.com",
    "public_base_url": "https://app.example.com",
    "smtp_host": "smtp.example.com",
    "token_encryption_keys": "t" * 40,
    "signup_mode": "invite",
    "email_verification_required": True,
    "gemini_api_key": "key",
    "llm_model": "model",
    "llm_daily_spend_ceiling_usd": 5.0,
}


def by_name(checks: list[Check]) -> dict[str, Check]:
    return {c.name: c for c in checks}


def test_a_complete_production_configuration_has_no_failure_and_no_warning(
    make_settings: Make,
) -> None:
    checks = settings_checks(make_settings(**PRODUCTION))
    assert worst(checks) == OK, [c for c in checks if c.level != OK]


def test_a_development_configuration_fails_the_production_checks(make_settings: Make) -> None:
    checks = by_name(settings_checks(make_settings()))
    for name in (
        "Environment",
        "Public address",
        "Allowed origins",
        "Token encryption keys",
        "Mail",
    ):
        assert checks[name].level == FAIL, name


def test_decisions_are_warnings_not_failures(make_settings: Make) -> None:
    open_signup = make_settings(**{**PRODUCTION, "signup_mode": "open"})
    no_spend = make_settings(**{**PRODUCTION, "llm_daily_spend_ceiling_usd": 0})
    no_model = make_settings(**{**PRODUCTION, "gemini_api_key": "", "llm_model": ""})
    no_verify = make_settings(**{**PRODUCTION, "email_verification_required": False})
    for settings, name in (
        (open_signup, "Sign-up"),
        (no_spend, "Spend ceiling"),
        (no_model, "Model"),
        (no_verify, "Verified email"),
    ):
        check = by_name(settings_checks(settings))[name]
        assert check.level == WARN, name
    assert worst(settings_checks(open_signup)) == WARN


def test_a_development_mail_catcher_is_not_a_real_mail_host(make_settings: Make) -> None:
    for host in ("mailpit", "localhost", "127.0.0.1"):
        assert (
            by_name(settings_checks(make_settings(**{**PRODUCTION, "smtp_host": host})))[
                "Mail"
            ].level
            == FAIL
        )


def test_no_check_prints_a_secret(make_settings: Make) -> None:
    settings = make_settings(**{**PRODUCTION, "gemini_api_key": "sk-very-secret-model-key"})
    text = " ".join(c.detail for c in settings_checks(settings))
    assert "sk-very-secret-model-key" not in text and "t" * 40 not in text and "k" * 40 not in text


def test_storage_must_be_writable(make_settings: Make, tmp_path: Path) -> None:
    ok = storage_checks(make_settings(file_storage_dir=str(tmp_path / "files")))
    assert ok[0].level == OK and (tmp_path / "files").is_dir()
    blocked = tmp_path / "blocked"
    blocked.write_text("a file, not a folder")
    assert storage_checks(make_settings(file_storage_dir=str(blocked / "inside")))[0].level == FAIL


def test_invalid_settings_are_one_clear_failure_and_nothing_else_runs() -> None:
    def broken() -> Settings:
        return Settings(_env_file=None, environment="production")  # type: ignore[call-arg]

    def never(_s: Settings) -> object:
        raise AssertionError("must not be called")

    checks = run_checks(broken, never)  # type: ignore[arg-type]
    assert len(checks) == 1 and checks[0].name == "Settings" and checks[0].level == FAIL
    assert "cannot be loaded" in checks[0].detail


def test_an_unreachable_database_is_a_failure_not_a_crash(
    make_settings: Make, tmp_path: Path
) -> None:
    settings = make_settings(file_storage_dir=str(tmp_path))
    from sqlalchemy import create_engine

    checks = run_checks(
        lambda: settings,
        lambda s: create_engine(
            s.database_url.get_secret_value(), connect_args={"connect_timeout": 1}
        ),
    )
    names = by_name(checks)
    assert names["Settings"].level == OK and names["Database"].level == FAIL


def test_worst_orders_fail_over_warning_over_ok() -> None:
    assert worst([Check("a", OK, ""), Check("b", WARN, "")]) == WARN
    assert worst([Check("a", WARN, ""), Check("b", FAIL, "")]) == FAIL
    assert worst([]) == OK


@pytest.mark.parametrize("name", ["Public address", "Allowed origins"])
def test_http_is_always_a_failure(make_settings: Make, name: str) -> None:
    settings = make_settings(
        **{
            **PRODUCTION,
            "environment": "development",
            "public_base_url": "http://x.example.com",
            "cors_origins": "http://x.example.com",
        }
    )
    assert by_name(settings_checks(settings))[name].level == FAIL
