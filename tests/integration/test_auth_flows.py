"""Authentication behavior against the real application and a real PostgreSQL."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from helpers import (
    PASSWORD,
    Account,
    RecordingMailer,
    generous_policies,
    make_invite,
    new_client,
    promote_to_admin,
    unique_email,
)
from sqlalchemy import update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_domain.auth import hash_token
from pv_domain.ratelimit import RatePolicy
from pv_persistence.models import EmailToken

pytestmark = pytest.mark.integration

MakeAccount = Callable[..., Account]
BuildApp = Callable[..., FastAPI]
BASE = "/api/v1/auth"


def test_register_signs_the_user_in(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    body = account.client.get(f"{BASE}/session").json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == account.email
    assert body["user"]["role"] == "USER"
    assert body["csrf_token"]


def test_anonymous_session_is_not_an_error(app: FastAPI) -> None:
    response = new_client(app).get(f"{BASE}/session")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["config"]["signup_mode"] == "invite"


def test_session_cookie_is_httponly_lax_and_site_wide(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    response = new_client(app).post(
        f"{BASE}/login", json={"email": account.email, "password": PASSWORD}
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie


def test_register_requires_a_valid_invite(app: FastAPI) -> None:
    response = new_client(app).post(
        f"{BASE}/register",
        json={"email": unique_email(), "password": PASSWORD, "invite_code": "not-a-real-code"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVITE_INVALID"


def test_register_without_invite_is_rejected(app: FastAPI) -> None:
    response = new_client(app).post(
        f"{BASE}/register", json={"email": unique_email(), "password": PASSWORD}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVITE_INVALID"


def test_invite_can_be_used_only_once(app: FastAPI, engine: Engine) -> None:
    code = make_invite(engine)
    first = new_client(app).post(
        f"{BASE}/register",
        json={"email": unique_email(), "password": PASSWORD, "invite_code": code},
    )
    second = new_client(app).post(
        f"{BASE}/register",
        json={"email": unique_email(), "password": PASSWORD, "invite_code": code},
    )
    assert first.status_code == 201
    assert second.status_code == 400


def test_email_bound_invite_rejects_a_different_email(app: FastAPI, engine: Engine) -> None:
    code = make_invite(engine, email="bound@example.com")
    response = new_client(app).post(
        f"{BASE}/register",
        json={"email": unique_email(), "password": PASSWORD, "invite_code": code},
    )
    assert response.status_code == 400


def test_weak_password_is_explained(app: FastAPI, engine: Engine) -> None:
    response = new_client(app).post(
        f"{BASE}/register",
        json={"email": unique_email(), "password": "short", "invite_code": make_invite(engine)},
    )
    assert response.status_code == 422
    assert "password" in response.json()["fields"]


def test_duplicate_email_is_a_conflict(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    response = new_client(app).post(
        f"{BASE}/register",
        json={
            "email": account.email.upper(),
            "password": PASSWORD,
            "invite_code": make_invite(engine),
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_TAKEN"


def test_login_failures_are_indistinguishable(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    client = new_client(app)
    wrong_password = client.post(
        f"{BASE}/login", json={"email": account.email, "password": "definitely not it"}
    )
    unknown_email = client.post(
        f"{BASE}/login", json={"email": unique_email(), "password": "definitely not it"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["code"] == unknown_email.json()["code"] == "INVALID_CREDENTIALS"
    assert wrong_password.json()["message"] == unknown_email.json()["message"]


def test_login_with_correct_password_works_case_insensitively(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    response = new_client(app).post(
        f"{BASE}/login", json={"email": account.email.upper(), "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_logout_revokes_the_session_on_the_server(
    app: FastAPI, make_account: MakeAccount, settings: Settings
) -> None:
    account = make_account(app)
    cookie_value = account.client.cookies.get(settings.session_cookie_name)
    assert cookie_value
    response = account.client.post(f"{BASE}/logout", headers=account.csrf)
    assert response.status_code == 200
    # Replay the old cookie from a different client: the server must refuse it.
    replay = new_client(app)
    replay.cookies.set(settings.session_cookie_name, cookie_value)
    assert replay.get(f"{BASE}/session").json()["authenticated"] is False


def test_csrf_token_is_required_for_state_changes(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    missing = account.client.post(f"{BASE}/logout")
    wrong = account.client.post(f"{BASE}/logout", headers={"X-CSRF-Token": "wrong"})
    assert missing.status_code == wrong.status_code == 403
    assert missing.json()["code"] == "CSRF_REJECTED"
    assert account.client.get(f"{BASE}/session").json()["authenticated"] is True


def test_foreign_origin_is_rejected(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    response = new_client(app).post(
        f"{BASE}/login",
        json={"email": account.email, "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_REJECTED"


def test_allowed_origin_is_accepted(
    app: FastAPI, make_account: MakeAccount, settings: Settings
) -> None:
    account = make_account(app)
    response = new_client(app).post(
        f"{BASE}/login",
        json={"email": account.email, "password": PASSWORD},
        headers={"Origin": settings.public_base_url},
    )
    assert response.status_code == 200


def test_password_change_rotates_and_revokes_other_sessions(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    other = new_client(app)
    assert (
        other.post(f"{BASE}/login", json={"email": account.email, "password": PASSWORD}).status_code
        == 200
    )

    new_password = "an entirely different passphrase"
    response = account.client.post(
        f"{BASE}/password/change",
        json={"current_password": PASSWORD, "new_password": new_password},
        headers=account.csrf,
    )
    assert response.status_code == 200
    assert account.client.get(f"{BASE}/session").json()["authenticated"] is True
    assert other.get(f"{BASE}/session").json()["authenticated"] is False
    assert (
        new_client(app)
        .post(f"{BASE}/login", json={"email": account.email, "password": PASSWORD})
        .status_code
        == 401
    )
    assert (
        new_client(app)
        .post(f"{BASE}/login", json={"email": account.email, "password": new_password})
        .status_code
        == 200
    )


def test_password_change_requires_the_current_password(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    response = account.client.post(
        f"{BASE}/password/change",
        json={
            "current_password": "wrong password here",
            "new_password": "an entirely different passphrase",
        },
        headers=account.csrf,
    )
    assert response.status_code == 422
    assert "current_password" in response.json()["fields"]


def test_forgot_password_answers_identically_and_mails_only_real_accounts(
    app: FastAPI, make_account: MakeAccount, mailer: RecordingMailer
) -> None:
    account = make_account(app)
    ghost = unique_email()
    client = new_client(app)
    known = client.post(f"{BASE}/password/forgot", json={"email": account.email})
    unknown = client.post(f"{BASE}/password/forgot", json={"email": ghost})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert any(to == account.email and "Reset" in subject for to, subject, _ in mailer.sent)
    assert not any(to == ghost for to, _, _ in mailer.sent)


def test_password_reset_flow_is_single_use_and_revokes_sessions(
    app: FastAPI, make_account: MakeAccount, mailer: RecordingMailer
) -> None:
    account = make_account(app)
    new_client(app).post(f"{BASE}/password/forgot", json={"email": account.email})
    token = mailer.last_token_for(account.email)
    client = new_client(app)

    weak = client.post(f"{BASE}/password/reset", json={"token": token, "new_password": "short"})
    assert weak.status_code == 422  # the link keeps working after a rejected password

    new_password = "a brand new strong passphrase"
    done = client.post(
        f"{BASE}/password/reset", json={"token": token, "new_password": new_password}
    )
    assert done.status_code == 200
    again = client.post(
        f"{BASE}/password/reset", json={"token": token, "new_password": new_password}
    )
    assert again.status_code == 400
    assert again.json()["code"] == "TOKEN_INVALID"

    assert account.client.get(f"{BASE}/session").json()["authenticated"] is False
    assert (
        new_client(app)
        .post(f"{BASE}/login", json={"email": account.email, "password": PASSWORD})
        .status_code
        == 401
    )
    assert (
        new_client(app)
        .post(f"{BASE}/login", json={"email": account.email, "password": new_password})
        .status_code
        == 200
    )


def test_expired_reset_token_is_rejected(
    app: FastAPI, make_account: MakeAccount, mailer: RecordingMailer, engine: Engine
) -> None:
    account = make_account(app)
    new_client(app).post(f"{BASE}/password/forgot", json={"email": account.email})
    token = mailer.last_token_for(account.email)
    with Session(engine) as db, db.begin():
        db.execute(
            update(EmailToken)
            .where(EmailToken.token_hash == hash_token(token))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
    response = new_client(app).post(
        f"{BASE}/password/reset",
        json={"token": token, "new_password": "a brand new strong passphrase"},
    )
    assert response.status_code == 400


def test_email_verification_flow(
    app: FastAPI, make_account: MakeAccount, mailer: RecordingMailer
) -> None:
    account = make_account(app)
    assert account.client.get(f"{BASE}/session").json()["user"]["email_verified"] is False
    token = mailer.last_token_for(account.email)
    confirm = new_client(app).post(f"{BASE}/email/verify/confirm", json={"token": token})
    assert confirm.status_code == 200
    assert account.client.get(f"{BASE}/session").json()["user"]["email_verified"] is True
    reuse = new_client(app).post(f"{BASE}/email/verify/confirm", json={"token": token})
    assert reuse.status_code == 400


def test_unverified_users_cannot_write_when_verification_is_required(
    build_app: BuildApp, make_account: MakeAccount, mailer: RecordingMailer
) -> None:
    app = build_app(email_verification_required=True)
    account = make_account(app)
    entry = {"entry_type": "skill", "data": {"name": "Python"}}
    blocked = account.client.post("/api/v1/profile/entries", json=entry, headers=account.csrf)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "EMAIL_NOT_VERIFIED"
    assert account.client.get("/api/v1/profile/entries").status_code == 200  # reading stays allowed

    token = mailer.last_token_for(account.email)
    assert (
        new_client(app).post(f"{BASE}/email/verify/confirm", json={"token": token}).status_code
        == 200
    )
    allowed = account.client.post("/api/v1/profile/entries", json=entry, headers=account.csrf)
    assert allowed.status_code == 201


def test_login_rate_limit_returns_a_structured_retry_hint(
    build_app: BuildApp,
) -> None:
    policies = {**generous_policies(), "login_ip": RatePolicy("login_ip", 3, 60)}
    app = build_app(policies)
    client = new_client(app)
    email = unique_email()
    statuses = [
        client.post(
            f"{BASE}/login", json={"email": email, "password": "wrong password!!"}
        ).status_code
        for _ in range(3)
    ]
    assert statuses == [401, 401, 401]
    limited = client.post(f"{BASE}/login", json={"email": email, "password": "wrong password!!"})
    assert limited.status_code == 429
    body = limited.json()
    assert body["code"] == "RATE_LIMITED"
    assert body["retry_after_seconds"] >= 1
    assert int(limited.headers["retry-after"]) >= 1


def test_admin_area_is_hidden_from_regular_users_and_open_to_admins(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    assert account.client.get("/api/v1/admin/overview").status_code == 404
    promote_to_admin(engine, account.email)
    response = account.client.get("/api/v1/admin/overview")
    assert response.status_code == 200
    assert response.json()["users"] >= 1


def test_protected_routes_need_a_session(app: FastAPI) -> None:
    response = new_client(app).get("/api/v1/profile/entries")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
