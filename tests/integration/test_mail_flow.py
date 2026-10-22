"""Email now travels through the queue. The API must say what it really does."""

import uuid
from collections.abc import Callable

from fastapi import FastAPI
from helpers import Account, RecordingMailer, new_client, unique_email
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

MakeAccount = Callable[..., Account]


def _tasks_for(engine: Engine, user_id: str) -> list[tuple[str, str, str | None]]:
    with Session(engine) as db:
        rows = db.execute(
            text(
                "SELECT task_type, state, payload->'args'->>'template' FROM tasks "
                "WHERE owner_user_id = :u ORDER BY created_at"
            ),
            {"u": uuid.UUID(user_id)},
        ).all()
    return [(r[0], r[1], r[2]) for r in rows]


def test_registration_queues_one_verification_email_and_sends_nothing_itself(
    app: FastAPI, make_account: MakeAccount, engine: Engine, mailer: RecordingMailer
) -> None:
    account = make_account(app)
    assert _tasks_for(engine, account.user_id) == [("send_email", "queued", "verify")]
    assert len(mailer.sent) == 1 and mailer.sent[0][0] == account.email


def test_verification_request_tells_the_truth_about_delivery(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    response = account.client.post("/api/v1/auth/email/verify/request", headers=account.csrf)
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_hint"] in {"log", "smtp_dev", "smtp"}
    assert "queued" in body["message"]
    assert "we sent" not in body["message"].lower()
    assert len(_tasks_for(engine, account.user_id)) == 2


def test_forgot_password_answers_identically_for_known_and_unknown_addresses(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    known = make_account(app)
    anonymous = new_client(app)
    for_known = anonymous.post("/api/v1/auth/password/forgot", json={"email": known.email})
    for_unknown = new_client(app).post(
        "/api/v1/auth/password/forgot", json={"email": unique_email()}
    )
    assert for_known.status_code == for_unknown.status_code == 202
    assert for_known.json() == for_unknown.json()
    assert ("send_email", "queued", "reset") in _tasks_for(engine, known.user_id)


def test_unknown_address_queues_nothing(
    app: FastAPI, engine: Engine, mailer: RecordingMailer
) -> None:
    new_client(app).post("/api/v1/auth/password/forgot", json={"email": unique_email()})
    assert mailer.sent == []


def test_hint_in_log_mode_points_at_the_worker_log(
    app: FastAPI, build_app: Callable[..., FastAPI], make_account: MakeAccount
) -> None:
    log_app = build_app(smtp_host="")
    account = make_account(log_app)
    body = account.client.post("/api/v1/auth/email/verify/request", headers=account.csrf).json()
    assert body["delivery_hint"] == "log"
    assert "worker log" in body["message"]


def test_hint_with_smtp_in_development_points_at_the_local_inbox(
    build_app: Callable[..., FastAPI], make_account: MakeAccount
) -> None:
    smtp_app = build_app(smtp_host="mailpit", dev_inbox_url="http://localhost:8025")
    account = make_account(smtp_app)
    body = account.client.post("/api/v1/auth/email/verify/request", headers=account.csrf).json()
    assert body["delivery_hint"] == "smtp_dev"
    assert "http://localhost:8025" in body["message"]


def test_the_queued_token_works_exactly_once(
    app: FastAPI, make_account: MakeAccount, mailer: RecordingMailer
) -> None:
    account = make_account(app)
    token = mailer.last_token_for(account.email)
    client = new_client(app)
    assert (
        client.post("/api/v1/auth/email/verify/confirm", json={"token": token}).status_code == 200
    )
    again = client.post("/api/v1/auth/email/verify/confirm", json={"token": token})
    assert again.status_code == 400 and again.json()["code"] == "TOKEN_INVALID"
