"""Facts about migration 0003 that the design depends on."""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pv_domain.states import RunState, StepState, TaskState


def _scalar(engine: Engine, sql: str, **params: object) -> object:
    with Session(engine) as db:
        return db.execute(text(sql), params).scalar_one()


def test_database_is_at_revision_0003_or_newer(engine: Engine) -> None:
    assert _scalar(engine, "SELECT version_num FROM alembic_version") >= "0003"  # type: ignore[operator]


@pytest.mark.parametrize(
    ("table", "rls"),
    [
        ("workflow_runs", True),
        ("workflow_steps", True),
        ("tasks", False),
        ("llm_calls", False),
        ("user_stats", False),
        ("worker_heartbeats", False),
    ],
)
def test_row_level_security_split(engine: Engine, table: str, rls: bool) -> None:
    with Session(engine) as db:
        row = db.execute(
            text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :n"),
            {"n": table},
        ).one()
    assert (row[0], row[1]) == (rls, rls)


def test_the_model_call_ledger_has_no_column_for_content(engine: Engine) -> None:
    with Session(engine) as db:
        columns = {
            r[0]
            for r in db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'llm_calls'"
                )
            )
        }
    assert "content_hash" in columns
    assert not {
        c
        for c in columns
        if any(w in c for w in ("prompt_text", "response", "content_text", "body", "text"))
    }


def test_the_application_role_cannot_rewrite_the_model_call_ledger(engine: Engine) -> None:
    with pytest.raises(DBAPIError), Session(engine) as db, db.begin():
        db.execute(text("UPDATE llm_calls SET purpose = 'x'"))
    with pytest.raises(DBAPIError), Session(engine) as db, db.begin():
        db.execute(text("DELETE FROM llm_calls"))


def test_task_error_text_is_limited_by_the_database_too(engine: Engine) -> None:
    with pytest.raises(DBAPIError), Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO tasks (task_type, idempotency_key, last_error) VALUES ('test.schema', :k, :e)"
            ),
            {"k": f"test.schema:{uuid.uuid4()}", "e": "x" * 301},
        )


@pytest.mark.parametrize("state", [s.value for s in TaskState])
def test_every_task_state_in_python_is_accepted_by_the_database(engine: Engine, state: str) -> None:
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO tasks (task_type, idempotency_key, state) VALUES ('test.schema', :k, :s)"
            ),
            {"k": f"test.schema:{uuid.uuid4()}", "s": state},
        )


def test_an_invalid_task_state_is_rejected(engine: Engine) -> None:
    with pytest.raises(DBAPIError), Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO tasks (task_type, idempotency_key, state) VALUES ('test.schema', :k, 'submitted')"
            ),
            {"k": f"test.schema:{uuid.uuid4()}"},
        )


def test_run_and_step_states_match_the_python_enums(engine: Engine) -> None:
    with Session(engine) as db:
        run_check = db.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'workflow_runs'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%needs_user_input%'"
            )
        ).scalar_one()
        step_check = db.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'workflow_steps'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%skipped%'"
            )
        ).scalar_one()
    assert all(f"'{s.value}'" in run_check for s in RunState)
    assert all(f"'{s.value}'" in step_check for s in StepState)


@pytest.fixture(autouse=True)
def _cleanup_schema_tasks(engine: Engine) -> Iterator[None]:
    yield
    with Session(engine) as db, db.begin():
        db.execute(text("DELETE FROM tasks WHERE task_type = 'test.schema'"))
