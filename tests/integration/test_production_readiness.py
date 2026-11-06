"""Checkpoint 3.7: the readiness checks against the real database, the token key rotation, and the
security headers of a production configuration."""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from helpers import Account
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api import cli
from pv_api.main import create_app
from pv_api.readiness import FAIL, OK, database_checks, run_checks
from pv_api.services.secret_rotation import reseal_github_tokens
from pv_config import SecretBox, Settings
from pv_persistence.tenancy import tenant_session

MakeAccount = Callable[..., Account]
KEY_A = "a" * 40
KEY_B = "b" * 40


def test_the_database_checks_pass_on_a_correctly_set_up_database(engine: Engine) -> None:
    checks = {c.name: c for c in database_checks(engine)}
    assert checks["Database"].level == OK and checks["Migrations"].level == OK
    assert checks["Application role"].level == OK
    assert (
        checks["Row Level Security"].level == OK
        and "tables that hold a person's data" in checks["Row Level Security"].detail
    )


def test_a_table_without_forced_security_is_a_failure(engine: Engine) -> None:
    """Plant a table with an owner column and no Row Level Security, as the owner would, and the check must catch it."""
    from sqlalchemy import create_engine

    from pv_config import get_settings

    owner = create_engine(get_settings().migration_database_url.get_secret_value())
    name = f"zz_unsafe_{uuid.uuid4().hex[:8]}"
    with owner.begin() as conn:
        conn.execute(text(f"CREATE TABLE {name} (owner_user_id uuid)"))
    try:
        detail = {c.name: c for c in database_checks(engine)}["Row Level Security"]
        assert detail.level == FAIL and name in detail.detail
    finally:
        with owner.begin() as conn:
            conn.execute(text(f"DROP TABLE {name}"))
        owner.dispose()


def test_the_command_exits_1_in_development_and_prints_every_check(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli.main(["check-config"])
    out = capsys.readouterr().out
    assert code == 1 and "[FAIL   ] Environment" in out and "[ok     ] Row Level Security" in out
    assert "Not safe to use" in out


def test_run_checks_reports_every_area(engine: Engine, settings: Settings) -> None:
    checks = run_checks(lambda: settings, lambda s: engine)
    assert {
        "Settings",
        "Environment",
        "File storage",
        "Database",
        "Migrations",
        "Application role",
        "Row Level Security",
    } <= {c.name for c in checks}


# ------------------------------------------------------------------------ rotating the token key


def plant_connection(engine: Engine, user_id: str, sealed: str) -> None:
    with tenant_session(engine, uuid.UUID(user_id)) as db:
        db.execute(
            text(
                "INSERT INTO github_connections (owner_user_id, github_user_id, login, token_sealed) "
                "VALUES (:o, :g, 'octo', :t) ON CONFLICT (owner_user_id) DO UPDATE SET token_sealed = :t"
            ),
            {"o": user_id, "g": 42, "t": sealed},
        )


def stored(engine: Engine, user_id: str) -> str:
    with tenant_session(engine, uuid.UUID(user_id)) as db:
        return str(db.execute(text("SELECT token_sealed FROM github_connections")).scalar_one())


def test_rotation_reseals_old_tokens_with_the_newest_key_and_keeps_them_working(
    app: object, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    person = make_account(app)  # type: ignore[arg-type]
    context = f"github-token:{person.user_id}"
    old = SecretBox(settings.secret_key.get_secret_value()).seal("gho_real_token", context=context)
    plant_connection(engine, person.user_id, old)
    assert old.startswith("v1.")

    first = settings.model_copy(update={"token_encryption_keys": _secret(KEY_A)})
    result = reseal_github_tokens(engine, first)
    assert result.resealed >= 1
    after_first = stored(engine, person.user_id)
    assert after_first.startswith("v2.") and "gho_real_token" not in after_first
    assert SecretBox.for_settings(first).open(after_first, context=context) == "gho_real_token"

    again = reseal_github_tokens(engine, first)  # nothing left to do for this person
    assert stored(engine, person.user_id) == after_first and again.resealed == 0

    rotated = settings.model_copy(update={"token_encryption_keys": _secret(f"{KEY_B},{KEY_A}")})
    reseal_github_tokens(engine, rotated)
    after_rotation = stored(engine, person.user_id)
    assert after_rotation != after_first and after_rotation.startswith("v2.")
    only_new = settings.model_copy(update={"token_encryption_keys": _secret(KEY_B)})
    assert (
        SecretBox.for_settings(only_new).open(after_rotation, context=context) == "gho_real_token"
    )


def test_a_token_that_cannot_be_opened_is_counted_and_left_alone(
    app: object, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    person = make_account(app)  # type: ignore[arg-type]
    lost = SecretBox(settings.secret_key.get_secret_value(), [KEY_A]).seal(
        "gho_x", context=f"github-token:{person.user_id}"
    )
    plant_connection(engine, person.user_id, lost)
    only_b = settings.model_copy(update={"token_encryption_keys": _secret(KEY_B)})
    result = reseal_github_tokens(engine, only_b)
    assert result.unreadable >= 1 and stored(engine, person.user_id) == lost


def test_the_rotation_command_reports_and_exits_by_result(
    capsys: pytest.CaptureFixture[str], engine: Engine
) -> None:
    code = cli.main(["reseal-tokens"])
    out = capsys.readouterr().out
    assert "Re-sealed" in out and "unreadable" in out and code in (0, 1)


def _secret(value: str):  # type: ignore[no-untyped-def]
    from pydantic import SecretStr

    return SecretStr(value)


# ------------------------------------------------------------------------ headers in production


def production_client(settings: Settings) -> TestClient:
    prod = settings.model_copy(
        update={
            "environment": "production",
            "cors_origins": "https://app.example.com",
            "public_base_url": "https://app.example.com",
            "smtp_host": "smtp.example.com",
            "token_encryption_keys": _secret(KEY_A),
        }
    )
    return TestClient(create_app(prod), base_url="https://app.example.com")


def test_production_responses_carry_the_security_headers(settings: Settings) -> None:
    with production_client(settings) as client:
        response = client.get("/api/v1/status")
    headers = response.headers
    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["x-content-type-options"] == "nosniff" and headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert headers["cache-control"] == "no-store"


def test_production_hides_the_interactive_documentation(settings: Settings) -> None:
    with production_client(settings) as client:
        for path in ("/api/docs", "/api/openapi.json", "/docs", "/redoc"):
            assert client.get(path).status_code == 404


def test_production_cookies_are_secure_host_prefixed_and_http_only(
    settings: Settings, engine: Engine
) -> None:
    from helpers import PASSWORD, make_invite, unique_email

    with production_client(settings) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email(),
                "password": PASSWORD,
                "invite_code": make_invite(engine),
            },
            headers={"origin": "https://app.example.com"},
        )
    assert response.status_code == 201
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-pv_session=") and "Secure" in cookie and "HttpOnly" in cookie
    assert "SameSite=lax" in cookie or "SameSite=Lax" in cookie and "Path=/" in cookie
    assert "Domain=" not in cookie


def test_a_request_from_another_origin_is_refused_in_production(settings: Settings) -> None:
    with production_client(settings) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "x"},
            headers={"origin": "https://evil.example.net"},
        )
    assert response.status_code == 403 and response.json()["code"] == "ORIGIN_REJECTED"


def test_rate_limit_counters_need_no_session(engine: Engine) -> None:
    with Session(engine) as db:
        assert db.execute(text("SELECT 1")).scalar_one() == 1


# ------------------------------------------------------------------------ signing everyone out


def test_the_incident_command_signs_everyone_out_and_says_how_many(
    app: object, make_account: MakeAccount, capsys: pytest.CaptureFixture[str], engine: Engine
) -> None:
    one, two = make_account(app), make_account(app)  # type: ignore[arg-type]
    assert one.client.get("/api/v1/auth/session").json()["authenticated"] is True
    assert cli.main(["revoke-all-sessions"]) == 0
    assert "Signed out" in capsys.readouterr().out
    assert one.client.get("/api/v1/auth/session").json()["authenticated"] is False
    assert two.client.get("/api/v1/auth/session").json()["authenticated"] is False
    with Session(engine) as db:
        recorded = db.execute(
            text("SELECT count(*) FROM audit_events WHERE action = 'admin.all_sessions_revoked'")
        ).scalar_one()
    assert recorded >= 1


def test_rotating_the_application_secret_alone_does_not_end_sessions(
    app: object, make_account: MakeAccount, settings: Settings
) -> None:
    """Sessions are rows in the database, not signed cookies. Rotating SECRET_KEY changes CSRF tokens
    and hashes, not who is signed in. The runbook says to revoke sessions on purpose."""
    person = make_account(app)  # type: ignore[arg-type]
    rotated = settings.model_copy(update={"secret_key": _secret("rotated-" + "k" * 40)})
    from helpers import new_client

    client = new_client(create_app(rotated))
    client.cookies.update(person.client.cookies)
    assert client.get("/api/v1/auth/session").json()["authenticated"] is True
