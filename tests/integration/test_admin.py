"""Administrator API: authorization on the server, guards, audit, and the no-tenant-data rule."""

import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from helpers import PASSWORD, Account, RecordingMailer, new_client, promote_to_admin, unique_email
from sqlalchemy import text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.services.admin_service import ensure_not_last_admin
from pv_persistence.models import ProfileEntry, User
from pv_persistence.tenancy import tenant_session

MakeAccount = Callable[..., Account]

GET_ROUTES = [
    "/api/v1/admin/overview",
    "/api/v1/admin/system",
    "/api/v1/admin/users",
    f"/api/v1/admin/users/{uuid.uuid4()}",
    "/api/v1/admin/invites",
    "/api/v1/admin/audit",
]
POST_ROUTES = [
    f"/api/v1/admin/users/{uuid.uuid4()}/{action}"
    for action in (
        "disable",
        "enable",
        "revoke-sessions",
        "promote",
        "demote",
        "resend-verification",
        "send-password-reset",
    )
] + [f"/api/v1/admin/tasks/{uuid.uuid4()}/requeue", f"/api/v1/admin/invites/{uuid.uuid4()}/revoke"]


@pytest.fixture
def admin(app: FastAPI, make_account: MakeAccount, engine: Engine) -> Account:
    account = make_account(app)
    promote_to_admin(engine, account.email)
    return account


@pytest.mark.parametrize("path", GET_ROUTES)
def test_regular_users_get_404_on_admin_reads(
    app: FastAPI, make_account: MakeAccount, path: str
) -> None:
    user = make_account(app)
    assert user.client.get(path).status_code == 404


@pytest.mark.parametrize("path", POST_ROUTES)
def test_regular_users_get_404_on_admin_writes_even_with_csrf(
    app: FastAPI, make_account: MakeAccount, path: str
) -> None:
    user = make_account(app)
    assert user.client.post(path, headers=user.csrf).status_code == 404


@pytest.mark.parametrize("path", GET_ROUTES)
def test_anonymous_callers_get_401_on_admin_reads(app: FastAPI, path: str) -> None:
    assert new_client(app).get(path).status_code == 401


@pytest.mark.parametrize("path", POST_ROUTES)
def test_admin_writes_need_the_csrf_token(admin: Account, path: str) -> None:
    response = admin.client.post(path)
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_REJECTED"


def test_user_list_finds_accounts_and_exposes_counters_only(
    app: FastAPI, make_account: MakeAccount, admin: Account
) -> None:
    target = make_account(app)
    response = admin.client.get("/api/v1/admin/users", params={"q": target.email})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["email"] == target.email
    assert row["profile_entries_count"] == 0 and row["runs_count"] == 0
    assert "password" not in response.text
    filtered = admin.client.get(
        "/api/v1/admin/users", params={"q": target.email, "status": "disabled"}
    )
    assert filtered.json()["total"] == 0


def test_admin_cannot_see_tenant_data_anywhere(
    app: FastAPI, make_account: MakeAccount, admin: Account, engine: Engine
) -> None:
    owner = make_account(app)
    marker = f"ZEBRA-{uuid.uuid4().hex}"
    with tenant_session(engine, uuid.UUID(owner.user_id)) as db:
        db.add(
            ProfileEntry(
                owner_user_id=uuid.UUID(owner.user_id),
                entry_type="project",
                data={"title": marker, "description": marker},
            )
        )
    detail = admin.client.get(f"/api/v1/admin/users/{owner.user_id}")
    assert detail.json()["user"]["profile_entries_count"] == 1  # a counter, not the content
    for path in GET_ROUTES[:3] + ["/api/v1/admin/invites", "/api/v1/admin/audit"]:
        assert marker not in admin.client.get(path).text
    assert marker not in detail.text


def test_disabling_an_account_ends_its_sessions_and_enabling_restores_sign_in(
    app: FastAPI, make_account: MakeAccount, admin: Account
) -> None:
    target = make_account(app)
    assert target.client.get("/api/v1/auth/session").json()["authenticated"] is True
    response = admin.client.post(
        f"/api/v1/admin/users/{target.user_id}/disable", headers=admin.csrf
    )
    assert response.status_code == 200
    assert target.client.get("/api/v1/auth/session").json()["authenticated"] is False
    login = new_client(app).post(
        "/api/v1/auth/login", json={"email": target.email, "password": PASSWORD}
    )
    assert login.status_code == 401
    assert (
        admin.client.post(
            f"/api/v1/admin/users/{target.user_id}/enable", headers=admin.csrf
        ).status_code
        == 200
    )
    login = new_client(app).post(
        "/api/v1/auth/login", json={"email": target.email, "password": PASSWORD}
    )
    assert login.status_code == 200


def test_an_admin_cannot_disable_themselves(admin: Account) -> None:
    response = admin.client.post(f"/api/v1/admin/users/{admin.user_id}/disable", headers=admin.csrf)
    assert response.status_code == 409
    assert response.json()["code"] == "SELF_ACTION_FORBIDDEN"


def test_revoke_sessions_signs_the_user_out(
    app: FastAPI, make_account: MakeAccount, admin: Account
) -> None:
    target = make_account(app)
    admin.client.post(f"/api/v1/admin/users/{target.user_id}/revoke-sessions", headers=admin.csrf)
    assert target.client.get("/api/v1/auth/session").json()["authenticated"] is False


def test_promote_and_demote(app: FastAPI, make_account: MakeAccount, admin: Account) -> None:
    target = make_account(app)
    assert (
        admin.client.post(
            f"/api/v1/admin/users/{target.user_id}/promote", headers=admin.csrf
        ).status_code
        == 200
    )
    assert target.client.get("/api/v1/admin/overview").status_code == 200
    again = admin.client.post(f"/api/v1/admin/users/{target.user_id}/promote", headers=admin.csrf)
    assert again.status_code == 409 and again.json()["code"] == "NO_CHANGE"
    assert (
        admin.client.post(
            f"/api/v1/admin/users/{target.user_id}/demote", headers=admin.csrf
        ).status_code
        == 200
    )
    assert target.client.get("/api/v1/admin/overview").status_code == 404


def test_the_last_active_admin_cannot_be_demoted_or_disabled(
    engine: Engine, admin: Account
) -> None:
    """Tested in a transaction that is rolled back, so real administrators are never touched."""
    with Session(engine) as db:
        db.execute(
            update(User)
            .where(User.role == "ADMIN", User.id != uuid.UUID(admin.user_id))
            .values(is_active=False)
        )
        target = db.get(User, uuid.UUID(admin.user_id))
        assert target is not None
        with pytest.raises(ApiError) as caught:
            ensure_not_last_admin(db, target)
        assert caught.value.code == "LAST_ADMIN"
        db.rollback()  # nothing above is ever committed


def test_invites_are_created_shown_once_used_and_revoked(
    app: FastAPI, admin: Account, engine: Engine
) -> None:
    created = admin.client.post("/api/v1/admin/invites", json={"days": 3}, headers=admin.csrf)
    assert created.status_code == 201
    code = created.json()["code"]
    invite_id = created.json()["invite"]["id"]
    assert created.json()["invite"]["created_by_email"] == admin.email
    listing = admin.client.get("/api/v1/admin/invites")
    assert code not in listing.text  # the code is never shown again

    joined = new_client(app).post(
        "/api/v1/auth/register",
        json={"email": unique_email(), "password": PASSWORD, "invite_code": code},
    )
    assert joined.status_code == 201
    revoked_used = admin.client.post(
        f"/api/v1/admin/invites/{invite_id}/revoke", headers=admin.csrf
    )
    assert revoked_used.status_code == 409

    second = admin.client.post("/api/v1/admin/invites", json={}, headers=admin.csrf).json()
    assert (
        admin.client.post(
            f"/api/v1/admin/invites/{second['invite']['id']}/revoke", headers=admin.csrf
        ).status_code
        == 200
    )
    blocked = new_client(app).post(
        "/api/v1/auth/register",
        json={"email": unique_email(), "password": PASSWORD, "invite_code": second["code"]},
    )
    assert blocked.status_code == 400 and blocked.json()["code"] == "INVITE_INVALID"
    statuses = {i["id"]: i["status"] for i in admin.client.get("/api/v1/admin/invites").json()}
    assert statuses[invite_id] == "used"
    assert statuses[second["invite"]["id"]] == "revoked"


def test_invite_can_be_bound_to_an_email_and_validates_it(app: FastAPI, admin: Account) -> None:
    bad = admin.client.post(
        "/api/v1/admin/invites", json={"email": "not-an-email"}, headers=admin.csrf
    )
    assert bad.status_code == 422
    assert (
        admin.client.post(
            "/api/v1/admin/invites", json={"days": 99}, headers=admin.csrf
        ).status_code
        == 422
    )
    bound = admin.client.post(
        "/api/v1/admin/invites", json={"email": unique_email()}, headers=admin.csrf
    ).json()
    wrong = new_client(app).post(
        "/api/v1/auth/register",
        json={"email": unique_email(), "password": PASSWORD, "invite_code": bound["code"]},
    )
    assert wrong.status_code == 400


def test_every_mutation_writes_an_audit_event_with_actor_and_target(
    app: FastAPI, make_account: MakeAccount, admin: Account
) -> None:
    target = make_account(app)
    admin.client.post(f"/api/v1/admin/users/{target.user_id}/revoke-sessions", headers=admin.csrf)
    events = admin.client.get("/api/v1/admin/audit", params={"action": "admin.sessions"}).json()[
        "items"
    ]
    mine = [e for e in events if e["target_id"] == target.user_id]
    assert mine and mine[0]["actor_email"] == admin.email
    assert mine[0]["category"] == "audit"
    detail = admin.client.get(f"/api/v1/admin/users/{target.user_id}").json()
    assert any(e["action"] == "admin.sessions_revoked" for e in detail["recent_events"])


def test_audit_pagination_and_filters(admin: Account) -> None:
    page = admin.client.get("/api/v1/admin/audit", params={"limit": 2, "category": "audit"})
    assert page.status_code == 200
    assert len(page.json()["items"]) <= 2
    assert admin.client.get("/api/v1/admin/audit", params={"limit": 1000}).status_code == 422


def test_resend_verification_and_password_reset_queue_mail(
    app: FastAPI, make_account: MakeAccount, admin: Account, mailer: RecordingMailer
) -> None:
    target = make_account(app)
    assert (
        admin.client.post(
            f"/api/v1/admin/users/{target.user_id}/resend-verification", headers=admin.csrf
        ).status_code
        == 200
    )
    assert (
        admin.client.post(
            f"/api/v1/admin/users/{target.user_id}/send-password-reset", headers=admin.csrf
        ).status_code
        == 200
    )
    templates = [subject for to, subject, _ in mailer.sent if to == target.email]
    assert any("Reset" in s for s in templates) and any("Confirm" in s for s in templates)
    token = mailer.last_token_for(target.email)
    assert (
        new_client(app)
        .post(
            "/api/v1/auth/password/reset",
            json={"token": token, "new_password": "another long passphrase 42"},
        )
        .status_code
        == 200
    )


def test_resend_verification_refuses_when_already_verified(
    app: FastAPI, make_account: MakeAccount, admin: Account, engine: Engine
) -> None:
    target = make_account(app)
    with Session(engine) as db, db.begin():
        db.execute(
            text("UPDATE users SET email_verified_at = now() WHERE id = :id"),
            {"id": uuid.UUID(target.user_id)},
        )
    response = admin.client.post(
        f"/api/v1/admin/users/{target.user_id}/resend-verification", headers=admin.csrf
    )
    assert response.status_code == 409 and response.json()["code"] == "ALREADY_VERIFIED"


def _insert_dead_letter(engine: Engine, task_type: str) -> uuid.UUID:
    task_id = uuid.uuid4()
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO tasks (id, task_type, idempotency_key, state, attempts, last_error, finished_at, payload) "
                "VALUES (:id, :t, :k, 'dead_letter', 3, 'boom', now(), '{\"args\": {}}')"
            ),
            {"id": task_id, "t": task_type, "k": f"test.admin:{task_id}"},
        )
    return task_id


def test_system_overview_lists_queue_workers_dead_letters_and_ai_usage(
    admin: Account, engine: Engine
) -> None:
    dead = _insert_dead_letter(engine, "test.admin.demo")
    body = admin.client.get("/api/v1/admin/system").json()
    assert set(body) == {"queue", "workers", "dead_letters", "ai_usage_24h"}
    assert "dead_letter" in body["queue"]["by_state"]
    letters = {d["id"]: d for d in body["dead_letters"]}
    assert letters[str(dead)]["last_error"] == "boom"
    assert letters[str(dead)]["requeueable"] is True
    assert {
        "calls",
        "errors",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "by_model",
    } <= set(body["ai_usage_24h"])
    assert "payload" not in admin.client.get("/api/v1/admin/system").text


def test_dead_letters_can_be_requeued_and_audit_records_it(admin: Account, engine: Engine) -> None:
    dead = _insert_dead_letter(engine, "test.admin.demo")
    assert (
        admin.client.post(f"/api/v1/admin/tasks/{dead}/requeue", headers=admin.csrf).status_code
        == 200
    )
    with Session(engine) as db:
        assert (
            db.execute(text("SELECT state FROM tasks WHERE id = :id"), {"id": dead}).scalar_one()
            == "queued"
        )
    again = admin.client.post(f"/api/v1/admin/tasks/{dead}/requeue", headers=admin.csrf)
    assert again.status_code == 409 and again.json()["code"] == "NOT_DEAD_LETTER"


def test_one_time_link_mail_cannot_be_requeued(admin: Account, engine: Engine) -> None:
    dead = _insert_dead_letter(engine, "send_email")
    try:
        letters = {
            d["id"]: d for d in admin.client.get("/api/v1/admin/system").json()["dead_letters"]
        }
        assert letters[str(dead)]["requeueable"] is False
        response = admin.client.post(f"/api/v1/admin/tasks/{dead}/requeue", headers=admin.csrf)
        assert response.status_code == 409 and response.json()["code"] == "NOT_REQUEUEABLE"
    finally:
        with Session(engine) as db, db.begin():
            db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": dead})


def test_unknown_task_and_user_ids_are_404(admin: Account) -> None:
    assert (
        admin.client.post(
            f"/api/v1/admin/tasks/{uuid.uuid4()}/requeue", headers=admin.csrf
        ).status_code
        == 404
    )
    assert admin.client.get(f"/api/v1/admin/users/{uuid.uuid4()}").status_code == 404
    assert (
        admin.client.post(
            f"/api/v1/admin/users/{uuid.uuid4()}/disable", headers=admin.csrf
        ).status_code
        == 404
    )


@pytest.fixture(autouse=True)
def _cleanup_demo_tasks(engine: Engine) -> Iterator[None]:
    yield
    with Session(engine) as db, db.begin():
        db.execute(text("DELETE FROM tasks WHERE task_type = 'test.admin.demo'"))
        db.execute(text("DELETE FROM tasks WHERE idempotency_key LIKE 'test.admin:%'"))
