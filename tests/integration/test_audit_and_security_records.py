from collections.abc import Callable

import pytest
from fastapi import FastAPI
from helpers import Account, new_client, unique_email
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

pytestmark = pytest.mark.integration

MakeAccount = Callable[..., Account]


def test_audit_log_cannot_be_updated(engine: Engine) -> None:
    with engine.connect() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("UPDATE audit_events SET action = 'tampered'"))


def test_audit_log_cannot_be_deleted_from(engine: Engine) -> None:
    with engine.connect() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("DELETE FROM audit_events"))


def test_registration_is_audited(app: FastAPI, make_account: MakeAccount, engine: Engine) -> None:
    account = make_account(app)
    with engine.connect() as conn:
        count = conn.execute(
            text(
                "SELECT count(*) FROM audit_events "
                "WHERE action = 'auth.register' AND actor_user_id = :u"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert count == 1


def test_failed_login_is_recorded_without_the_plain_email(app: FastAPI, engine: Engine) -> None:
    email = unique_email()
    new_client(app).post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong password!!"}
    )
    with engine.connect() as conn:
        failures = conn.execute(
            text(
                "SELECT count(*) FROM audit_events "
                "WHERE action = 'auth.login_failed' AND category = 'security'"
            )
        ).scalar_one()
        leaks = conn.execute(
            text(
                "SELECT count(*) FROM audit_events "
                "WHERE position(CAST(:e AS text) IN metadata::text) > 0"
            ),
            {"e": email},
        ).scalar_one()
    assert failures >= 1
    assert leaks == 0


def test_rate_limit_table_is_writable_but_bucket_keys_hold_no_raw_email(
    app: FastAPI, engine: Engine
) -> None:
    email = unique_email()
    new_client(app).post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong password!!"}
    )
    with engine.connect() as conn:
        leaks = conn.execute(
            text(
                "SELECT count(*) FROM rate_limit_buckets "
                "WHERE position(CAST(:e AS text) IN bucket_key) > 0"
            ),
            {"e": email},
        ).scalar_one()
    assert leaks == 0
