"""Checkpoint 3.7: a copy of your data, and deleting the account, against the real database.

The deletion test is the one that matters: after the worker task has run, nothing that belongs to
the person is left. It does not trust a list of tables. It walks every foreign key that points at
users and every table that has an owner column, so a table added in the future is checked too.
"""

import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import PASSWORD, Account, make_invite, new_client, promote_to_admin
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from test_analysis import read_job
from test_reports import ask, make_context, run_build
from test_resume_images import add as add_image
from test_resume_profile import upload as upload_resume
from test_studio import make_doc

from pv_config import Settings
from pv_files import FileStorage, StorageError, new_export_key
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.delete_account import run_delete

ACCOUNT = "/api/v1/account"
CONFIRM = "delete my account"
MakeAccount = Callable[..., Account]


def ask_delete(account: Account, **body: Any) -> Any:
    payload = {"password": PASSWORD, "confirm": CONFIRM, **body}
    return account.client.post(f"{ACCOUNT}/delete", json=payload, headers=account.csrf)


def deletion_context(
    engine: Engine, settings: Settings, user_id: str, *, attempt: int = 1, max_attempts: int = 6
) -> TaskContext:
    with Session(engine) as db:
        row = db.execute(
            text(
                "SELECT id, payload FROM tasks WHERE task_type = 'delete_account' "
                "AND payload->'args'->>'user_id' = :u ORDER BY created_at DESC LIMIT 1"
            ),
            {"u": user_id},
        ).one()
    return TaskContext(
        task_id=row.id, task_type="delete_account", args=row.payload["args"], secret={},
        attempt=attempt, max_attempts=max_attempts, owner_user_id=None, run_id=None,
        settings=settings, engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def seed_person(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> tuple[Account, list[str]]:
    """A person with data in many places, and the stored files that belong to them."""
    account = make_account(app)
    headers = account.csrf
    for entry in (
        {"entry_type": "skill", "data": {"name": "SQL"}},
        {"entry_type": "skill", "data": {"name": "Python"}},
    ):
        assert (
            account.client.post("/api/v1/profile/entries", json=entry, headers=headers).status_code
            == 201
        )
    assert (
        account.client.put(
            "/api/v1/profile/preferences",
            json={"locations": ["Pune"], "needs_sponsorship": False},
            headers=headers,
        ).status_code
        == 200
    )
    job_id = read_job(engine, settings, account)
    assert (
        account.client.post(
            f"/api/v1/jobs/{job_id}/decision", json={"action": "save"}, headers=headers
        ).status_code
        == 200
    )
    assert upload_resume(account).status_code == 201
    add_image(account, 1)
    make_doc(account, start="blank")
    report = ask(account).json()
    run_build(make_context(engine, settings, account, report["id"]), storage=storage)
    # A stored PDF of a studio resume, and a queued unused import file, set up directly.
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:
        doc_id = db.execute(text("SELECT id FROM resume_documents LIMIT 1")).scalar_one()
        pdf_key = new_export_key()
        storage.put(pdf_key, b"%PDF-1.4 test")
        db.execute(
            text(
                "INSERT INTO resume_exports (owner_user_id, document_id, revision, status, storage_key) "
                "VALUES (:o, :d, 1, 'ready', :k)"
            ),
            {"o": uid, "d": doc_id, "k": pdf_key},
        )
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO rate_limit_buckets (bucket_key, window_start, hits) VALUES (:k, now(), 3)"
            ),
            {"k": f"studio_export_user:{uid}"},
        )
    with tenant_session(engine, uid) as db:
        keys = [
            str(k)
            for table, col in (
                ("resumes", "storage_key"), ("resume_images", "storage_key"),
                ("resume_exports", "storage_key"), ("report_exports", "storage_key"),
            )
            for k in db.execute(text(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL")).scalars()
        ]  # fmt: skip
    return account, keys


# ------------------------------------------------------------------------ the copy of your data


def test_you_can_download_a_copy_of_your_data(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = seed_person(app, make_account, engine, settings, storage)
    response = account.client.get(f"{ACCOUNT}/export")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="Provenance data.json"'
    assert (
        "no-store" in response.headers["cache-control"]
        and response.headers["x-content-type-options"] == "nosniff"
    )
    data = json.loads(response.content)
    assert data["export_version"] == 1 and data["account"]["email"] == account.email
    assert {e["data"]["name"] for e in data["profile_entries"]} >= {"SQL", "Python"}
    assert data["preferences"]["locations"] == ["Pune"]
    assert len(data["resumes_made_in_the_studio"]) >= 1 and len(data["jobs"]) == 1
    assert data["jobs"][0]["posting_text"] and data["jobs"][0]["title"]
    assert "does not include your password" in data["about"]


def test_the_copy_never_holds_a_secret_or_a_storage_key_or_someone_else(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, keys = seed_person(app, make_account, engine, settings, storage)
    other = make_account(app)
    other_job = read_job(engine, settings, other)
    raw = account.client.get(f"{ACCOUNT}/export").text
    assert "password_hash" not in raw and "argon2" not in raw
    assert "token_sealed" not in raw and "csrf" not in raw.lower()
    for key in keys:
        assert key not in raw
    assert other.email not in raw and other_job not in raw


def test_the_copy_needs_a_signed_in_person_and_is_rate_limited(
    app: FastAPI, make_account: MakeAccount
) -> None:
    assert new_client(app).get(f"{ACCOUNT}/export").status_code == 401
    account = make_account(app)
    from pv_domain.ratelimit import DEFAULT_POLICIES

    assert DEFAULT_POLICIES["account_export_user"].limit == 3
    assert account.client.get(f"{ACCOUNT}/export").status_code == 200


# ------------------------------------------------------------------------ asking to delete


def test_deleting_needs_the_right_password_and_the_words_typed(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    wrong = ask_delete(account, password="not my password")
    assert wrong.status_code == 422 and "password" in wrong.json()["fields"]
    typed = ask_delete(account, confirm="yes")
    assert typed.status_code == 422 and "confirm" in typed.json()["fields"]
    assert (
        account.client.get("/api/v1/auth/session").json()["authenticated"] is True
    )  # nothing happened
    assert (
        ask_delete(account, confirm="  Delete   MY account ").status_code == 202
    )  # case and spacing do not matter


def test_deleting_needs_csrf_and_a_session(app: FastAPI, make_account: MakeAccount) -> None:
    assert (
        new_client(app)
        .post(f"{ACCOUNT}/delete", json={"password": PASSWORD, "confirm": CONFIRM})
        .status_code
        == 401
    )
    account = make_account(app)
    refused = account.client.post(
        f"{ACCOUNT}/delete", json={"password": PASSWORD, "confirm": CONFIRM}
    )
    assert refused.status_code in (400, 403)


def test_asking_signs_you_out_everywhere_and_blocks_signing_in(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    second = new_client(app)
    assert (
        second.post(
            "/api/v1/auth/login", json={"email": account.email, "password": PASSWORD}
        ).status_code
        == 200
    )
    response = ask_delete(account)
    assert response.status_code == 202 and "deleted" in response.json()["message"]
    assert account.client.get("/api/v1/auth/session").json()["authenticated"] is False
    assert second.get("/api/v1/auth/session").json()["authenticated"] is False
    retry = new_client(app).post(
        "/api/v1/auth/login", json={"email": account.email, "password": PASSWORD}
    )
    assert retry.status_code in (401, 403)


def test_asking_twice_is_harmless(app: FastAPI, make_account: MakeAccount, engine: Engine) -> None:
    account = make_account(app)
    assert ask_delete(account).status_code == 202
    with Session(engine) as db:
        count = db.execute(
            text(
                "SELECT count(*) FROM tasks WHERE task_type = 'delete_account' AND payload->'args'->>'user_id' = :u"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert count == 1


def test_the_only_administrator_cannot_delete_themselves(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    with Session(engine) as db, db.begin():
        db.execute(text("UPDATE users SET role = 'USER' WHERE role = 'ADMIN'"))
    admin = make_account(app)
    promote_to_admin(engine, admin.email)
    refused = ask_delete(admin)
    assert refused.status_code == 409 and refused.json()["code"] == "LAST_ADMIN"
    assert admin.client.get("/api/v1/auth/session").json()["authenticated"] is True


def test_asking_is_rate_limited_and_audited(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    from pv_domain.ratelimit import DEFAULT_POLICIES

    assert DEFAULT_POLICIES["account_delete_user"].limit == 5
    account = make_account(app)
    ask_delete(account, password="wrong")
    with Session(engine) as db:
        actions = set(
            db.execute(
                text("SELECT action FROM audit_events WHERE actor_user_id = :u"),
                {"u": account.user_id},
            ).scalars()
        )
    assert "account.deletion_password_failed" in actions


# ------------------------------------------------------------------------ the deletion itself


def references_to_users(engine: Engine) -> list[tuple[str, str, str]]:
    """(table, column, on delete action) for every foreign key that points at users."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT cl.relname, a.attname, c.confdeltype
                FROM pg_constraint c
                JOIN pg_class cl ON cl.oid = c.conrelid
                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
                WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass
                ORDER BY 1, 2
                """
            )
        ).all()
    return [(str(t), str(c), str(d)) for t, c, d in rows]


def test_every_table_that_names_a_person_either_cascades_or_clears(engine: Engine) -> None:
    """A table added later with a plain foreign key to users would block deletion. This fails first."""
    allowed = {"c", "n"}  # CASCADE or SET NULL
    bad = [(t, c, d) for t, c, d in references_to_users(engine) if d not in allowed]
    assert bad == [], f"These references would block or ignore deletion: {bad}"
    tables = {t for t, _c, _d in references_to_users(engine)}
    assert len(tables) > 30


def test_after_the_task_runs_nothing_of_the_person_is_left(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, keys = seed_person(app, make_account, engine, settings, storage)
    bystander = make_account(app)
    bystander_job = read_job(engine, settings, bystander)
    uid = account.user_id
    assert len(keys) >= 4 and all(storage.exists(k) for k in keys)
    bound = make_invite(engine, account.email)  # an invite bound to this person's address
    assert bound
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO tasks (task_type, payload, idempotency_key) VALUES ('send_email', CAST(:p AS jsonb), :k)"
            ),
            {
                "p": json.dumps({"args": {}, "secret": {"to": account.email, "token": "t"}}),
                "k": f"mail-{uuid.uuid4()}",
            },
        )

    assert ask_delete(account).status_code == 202
    run_delete(deletion_context(engine, settings, uid), storage=storage)

    # The files are gone.
    assert not any(storage.exists(k) for k in keys)
    # The user is gone, and so is every row that referenced them.
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM users WHERE id = :u"), {"u": uid}).scalar_one()
            == 0
        )
        for table, column, _action in references_to_users(engine):
            left = conn.execute(
                text(f'SELECT count(*) FROM "{table}" WHERE "{column}" = :u'), {"u": uid}
            ).scalar_one()
            assert left == 0, f"{table}.{column} still names the person"
        # The strays the cascade cannot reach.
        assert (
            conn.execute(
                text("SELECT count(*) FROM rate_limit_buckets WHERE bucket_key LIKE :s"),
                {"s": f"%:{uid}"},
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM invites WHERE lower(email) = lower(:e)"),
                {"e": account.email},
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM tasks WHERE lower(payload->'secret'->>'to') = lower(:e)"
                ),
                {"e": account.email},
            ).scalar_one()
            == 0
        )
        # No audit record carries the address, and the actor was cleared.
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_events WHERE metadata::text ILIKE :e"),
                {"e": f"%{account.email}%"},
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_events WHERE actor_user_id = :u"), {"u": uid}
            ).scalar_one()
            == 0
        )
        # The model call log kept its counts and lost the person.
        assert (
            conn.execute(
                text("SELECT count(*) FROM llm_calls WHERE user_id = :u"), {"u": uid}
            ).scalar_one()
            == 0
        )
    # Every tenant table, found by its owner column, has no row for the person.
    with engine.connect() as conn:
        owner_tables = [
            str(r[0])
            for r in conn.execute(
                text(
                    "SELECT table_name FROM information_schema.columns WHERE table_schema = 'public' AND column_name = 'owner_user_id'"
                )
            )
        ]
        for table in owner_tables:
            assert (
                conn.execute(
                    text(f'SELECT count(*) FROM "{table}" WHERE owner_user_id = :u'), {"u": uid}
                ).scalar_one()
                == 0
            ), table
    # The person's own sessions no longer exist, and the bystander is untouched.
    assert bystander.client.get("/api/v1/auth/session").json()["authenticated"] is True
    assert bystander.client.get("/api/v1/jobs").status_code == 200
    with tenant_session(engine, uuid.UUID(bystander.user_id)) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM job_postings WHERE id = :i"), {"i": bystander_job}
            ).scalar_one()
            == 1
        )


def test_the_record_of_a_deletion_names_no_one(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, keys = seed_person(app, make_account, engine, settings, storage)
    ask_delete(account)
    run_delete(deletion_context(engine, settings, account.user_id), storage=storage)
    with engine.connect() as conn:
        columns = [
            str(r[0])
            for r in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'account_deletions'"
                )
            )
        ]
        newest = conn.execute(
            text(
                "SELECT status, files_removed, stray_rows_removed, error_code FROM account_deletions ORDER BY requested_at DESC LIMIT 1"
            )
        ).one()
    assert not {"user_id", "email", "owner_user_id"} & set(columns)
    assert (
        newest.status == "done"
        and newest.files_removed >= len(keys) - 0
        and newest.error_code is None
    )


def test_the_task_is_safe_to_run_again(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = seed_person(app, make_account, engine, settings, storage)
    ask_delete(account)
    context = deletion_context(engine, settings, account.user_id)
    run_delete(context, storage=storage)
    run_delete(context, storage=storage)  # the person is already gone: finishes quietly
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM users WHERE id = :u"), {"u": account.user_id}
            ).scalar_one()
            == 0
        )


class FlakyStorage:
    def __init__(self, inner: FileStorage) -> None:
        self.inner = inner
        self.fail = True

    def put(self, key: str, data: bytes) -> None:
        self.inner.put(key, data)

    def get(self, key: str) -> bytes:
        return self.inner.get(key)

    def delete(self, key: str) -> None:
        if self.fail:
            raise StorageError("disk")
        self.inner.delete(key)

    def exists(self, key: str) -> bool:
        return self.inner.exists(key)


def test_a_storage_error_retries_and_removes_nothing_until_the_files_are_gone(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, keys = seed_person(app, make_account, engine, settings, storage)
    ask_delete(account)
    flaky = FlakyStorage(storage)
    with pytest.raises(TaskFailure) as first:
        run_delete(deletion_context(engine, settings, account.user_id, attempt=1), storage=flaky)
    assert first.value.retryable
    with engine.connect() as conn:  # the person's rows are still there: nothing was removed early
        assert (
            conn.execute(
                text("SELECT count(*) FROM users WHERE id = :u"), {"u": account.user_id}
            ).scalar_one()
            == 1
        )
    flaky.fail = False
    run_delete(deletion_context(engine, settings, account.user_id, attempt=2), storage=flaky)
    assert not any(storage.exists(k) for k in keys)
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM users WHERE id = :u"), {"u": account.user_id}
            ).scalar_one()
            == 0
        )


def test_a_last_attempt_that_cannot_remove_files_is_marked_failed_and_keeps_the_data(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = seed_person(app, make_account, engine, settings, storage)
    ask_delete(account)
    run_delete(
        deletion_context(engine, settings, account.user_id, attempt=6, max_attempts=6),
        storage=FlakyStorage(storage),
    )
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM users WHERE id = :u"), {"u": account.user_id}
            ).scalar_one()
            == 1
        )
        status = conn.execute(
            text(
                "SELECT status, error_code FROM account_deletions ORDER BY requested_at DESC LIMIT 1"
            )
        ).one()
    assert status.status == "failed" and status.error_code == "STORAGE_FAILED"


def test_the_deletion_record_cannot_be_removed_by_the_application(engine: Engine) -> None:
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError), Session(engine) as db, db.begin():
        db.execute(text("DELETE FROM account_deletions"))
