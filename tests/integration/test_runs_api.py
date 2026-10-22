"""Runs: user-facing API, tenant isolation (RLS plus owner filters) and the admin counters."""

import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi import FastAPI
from helpers import Account, new_client
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pv_domain.states import RunState, StepState
from pv_persistence.llm_usage import record_llm_call
from pv_persistence.models import ProfileEntry
from pv_persistence.runs import add_step, create_run, set_run_state
from pv_persistence.tenancy import tenant_session

MakeAccount = Callable[..., Account]


def _make_run(engine: Engine, account: Account, *, failed: bool = False) -> uuid.UUID:
    user_id = uuid.UUID(account.user_id)
    with tenant_session(engine, user_id) as db:
        run = create_run(db, owner_user_id=user_id, workflow_type="job_analysis")
        set_run_state(db, run.id, RunState.RUNNING)
        add_step(
            db,
            run_id=run.id,
            owner_user_id=user_id,
            step_name="Extract requirements",
            ordinal=1,
            state=StepState.SUCCEEDED,
            duration_ms=400,
        )
        add_step(
            db,
            run_id=run.id,
            owner_user_id=user_id,
            step_name="Resolve evidence",
            ordinal=2,
            state=StepState.FAILED if failed else StepState.SUCCEEDED,
            duration_ms=900,
            error_message="provider busy" if failed else "",
        )
        if failed:
            set_run_state(
                db,
                run.id,
                RunState.FAILED,
                can_retry=True,
                error_class="TRANSIENT",
                error_type="LLMError",
                error_message="provider busy",
            )
        else:
            set_run_state(db, run.id, RunState.SUCCEEDED)
        return run.id


def test_runs_require_sign_in(app: FastAPI) -> None:
    assert new_client(app).get("/api/v1/runs").status_code == 401


def test_a_user_sees_only_their_own_runs(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    alice, bob = make_account(app), make_account(app)
    run_id = _make_run(engine, alice)
    listing = alice.client.get("/api/v1/runs").json()
    assert [r["id"] for r in listing["items"]] == [str(run_id)]
    assert listing["items"][0]["workflow_label"] == "Job analysis"
    assert listing["items"][0]["ui_state"] == "completed"
    assert bob.client.get("/api/v1/runs").json() == {
        "items": [],
        "total": 0,
        "limit": 25,
        "offset": 0,
    }
    assert bob.client.get(f"/api/v1/runs/{run_id}").status_code == 404
    assert (
        bob.client.get(f"/api/v1/runs/{uuid.uuid4()}").status_code == 404
    )  # same answer as a foreign id


def test_run_detail_shows_steps_in_order_and_model_usage(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    alice = make_account(app)
    run_id = _make_run(engine, alice)
    record_llm_call(
        engine,
        purpose="extract",
        provider="gemini",
        model="some-model",
        input_tokens=120,
        output_tokens=30,
        estimated_cost_usd=Decimal("0.001500"),
        latency_ms=800,
        run_id=run_id,
        user_id=uuid.UUID(alice.user_id),
        prompt_version="extract.v1",
    )
    # A row for the same run attributed to someone else must never be shown (owner filter).
    other = make_account(app)
    record_llm_call(
        engine,
        purpose="intruder",
        provider="gemini",
        model="m",
        input_tokens=1,
        output_tokens=1,
        estimated_cost_usd=Decimal(0),
        latency_ms=1,
        run_id=run_id,
        user_id=uuid.UUID(other.user_id),
    )
    detail = alice.client.get(f"/api/v1/runs/{run_id}").json()
    assert [s["step_name"] for s in detail["steps"]] == ["Extract requirements", "Resolve evidence"]
    assert detail["run"]["duration_ms"] is not None
    assert [c["purpose"] for c in detail["llm_calls"]] == ["extract"]
    assert detail["llm_calls"][0]["estimated_cost_usd"] == 0.0015
    assert detail["llm_calls"][0]["prompt_version"] == "extract.v1"


def test_a_failed_run_that_can_be_retried_says_so(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    alice = make_account(app)
    run_id = _make_run(engine, alice, failed=True)
    detail = alice.client.get(f"/api/v1/runs/{run_id}").json()
    assert detail["run"]["ui_state"] == "retry_available"
    assert "provider busy" in detail["error_summary"]
    assert detail["steps"][1]["ui_state"] == "permanently_failed"


def test_runs_list_pagination_is_bounded(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    alice = make_account(app)
    for _ in range(3):
        _make_run(engine, alice)
    page = alice.client.get("/api/v1/runs", params={"limit": 2}).json()
    assert len(page["items"]) == 2 and page["total"] == 3
    assert alice.client.get("/api/v1/runs", params={"limit": 101}).status_code == 422


def test_row_level_security_hides_runs_from_raw_sql(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    alice, bob = make_account(app), make_account(app)
    run_id = _make_run(engine, alice)
    with Session(engine) as db, db.begin():  # no tenant context: fails closed
        assert db.execute(text("SELECT count(*) FROM workflow_runs")).scalar_one() == 0
    with tenant_session(engine, uuid.UUID(bob.user_id)) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM workflow_runs WHERE id = :id"), {"id": run_id}
            ).scalar_one()
            == 0
        )
        assert (
            db.execute(
                text("SELECT count(*) FROM workflow_steps WHERE run_id = :id"), {"id": run_id}
            ).scalar_one()
            == 0
        )
    with pytest.raises(DBAPIError), tenant_session(engine, uuid.UUID(bob.user_id)) as db:
        db.execute(
            text("INSERT INTO workflow_runs (owner_user_id, workflow_type) VALUES (:o, 'demo')"),
            {"o": uuid.UUID(alice.user_id)},
        )


def test_admin_counters_follow_runs_and_profile_entries(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    alice = make_account(app)
    user_id = uuid.UUID(alice.user_id)

    def counters() -> tuple[int, int]:
        with Session(engine) as db:
            row = db.execute(
                text("SELECT profile_entries_count, runs_count FROM user_stats WHERE user_id = :u"),
                {"u": user_id},
            ).one()
        return row[0], row[1]

    assert counters() == (0, 0)
    _make_run(engine, alice)
    with tenant_session(engine, user_id) as db:
        entry = ProfileEntry(owner_user_id=user_id, entry_type="skill", data={"name": "x"})
        db.add(entry)
        db.flush()
        entry_id = entry.id
    assert counters() == (1, 1)
    with tenant_session(engine, user_id) as db:
        db.execute(text("DELETE FROM profile_entries WHERE id = :id"), {"id": entry_id})
    assert counters() == (0, 1)
