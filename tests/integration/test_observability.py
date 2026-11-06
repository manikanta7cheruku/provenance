"""Checkpoint 3.5: the admin console's answers and the Run Inspector, against the real database.

The tests share one database with every other test, so they plant rows they can recognize (a
unique model name, a unique task type) and assert on those, never on whole-system totals.
"""

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account, new_client, promote_to_admin
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api import cli
from pv_domain.states import RunState, StepState
from pv_persistence.audit import record_audit
from pv_persistence.llm_usage import record_llm_call
from pv_persistence.queue import enqueue
from pv_persistence.runs import add_step, create_run, set_run_state
from pv_persistence.tenancy import tenant_session

MakeAccount = Callable[..., Account]
ADMIN = "/api/v1/admin"


@pytest.fixture
def admin(app: FastAPI, make_account: MakeAccount, engine: Engine) -> Account:
    account = make_account(app)
    promote_to_admin(engine, account.email)
    return account


def plant_task(engine: Engine, task_type: str, state: str, **extra: Any) -> uuid.UUID:
    with Session(engine) as db, db.begin():
        task_id = enqueue(
            db,
            task_type=task_type,
            idempotency_key=f"{task_type}:{uuid.uuid4().hex}",
            run_id=extra.get("run_id"),
            owner_user_id=extra.get("owner"),
        )
        assert task_id is not None
        db.execute(
            text(
                "UPDATE tasks SET state = :s, attempts = :a, last_error = :e, "
                "locked_until = :l, finished_at = :f WHERE id = :i"
            ),
            {
                "s": state,
                "a": extra.get("attempts", 1),
                "e": extra.get("error"),
                "l": extra.get("locked_until"),
                "f": datetime.now(UTC) if state in ("dead_letter", "succeeded") else None,
                "i": task_id,
            },
        )
    return task_id


def cleanup_tasks(engine: Engine, *ids: uuid.UUID) -> None:
    with Session(engine) as db, db.begin():
        for task_id in ids:
            db.execute(text("DELETE FROM tasks WHERE id = :i"), {"i": task_id})


def make_run(
    engine: Engine, account: Account, *, failed: bool, subject: str | None = None
) -> uuid.UUID:
    user_id = uuid.UUID(account.user_id)
    with tenant_session(engine, user_id) as db:
        run = create_run(
            db,
            owner_user_id=user_id,
            workflow_type="job_analysis",
            subject_type="job_posting" if subject else None,
            subject_id=subject,
        )
        set_run_state(db, run.id, RunState.RUNNING)
        add_step(
            db, run_id=run.id, owner_user_id=user_id, step_name="gather_jobs", ordinal=1,
            state=StepState.SUCCEEDED, duration_ms=120, detail={"jobs": 7, "note": "text", "flag": True},
        )  # fmt: skip
        add_step(
            db, run_id=run.id, owner_user_id=user_id, step_name="write_file", ordinal=2,
            state=StepState.FAILED if failed else StepState.SUCCEEDED, duration_ms=300,
            error_message="provider busy" if failed else "",
        )  # fmt: skip
        if failed:
            set_run_state(
                db, run.id, RunState.FAILED, can_retry=True, error_class="JOB_ANALYSIS_FAILED",
                error_type="LLMError", error_message="provider busy",
            )  # fmt: skip
        else:
            set_run_state(db, run.id, RunState.SUCCEEDED)
        return run.id


def call(engine: Engine, run_id: uuid.UUID | None, user: str | None, **over: Any) -> None:
    values: dict[str, Any] = {
        "purpose": "extract", "provider": "gemini", "model": "model-x", "input_tokens": 100,
        "output_tokens": 20, "estimated_cost_usd": Decimal("0.002"), "latency_ms": 500,
        "prompt_version": "extract.v1",
    }  # fmt: skip
    values.update(over)
    record_llm_call(engine, run_id=run_id, user_id=uuid.UUID(user) if user else None, **values)


# ------------------------------------------------------------------------ who may ask


@pytest.mark.parametrize(
    "path",
    [
        f"{ADMIN}/health",
        f"{ADMIN}/usage",
        f"{ADMIN}/usage?days=30",
        f"{ADMIN}/trace/{uuid.uuid4()}",
    ],
)
def test_only_an_admin_sees_the_console(app: FastAPI, make_account: MakeAccount, path: str) -> None:
    assert new_client(app).get(path).status_code in (401, 404)
    user = make_account(app)
    assert user.client.get(path).status_code == 404


def test_usage_accepts_only_the_two_windows(admin: Account) -> None:
    assert admin.client.get(f"{ADMIN}/usage?days=90").status_code == 422
    assert admin.client.get(f"{ADMIN}/usage?days=abc").status_code == 422


# ------------------------------------------------------------------------ is it healthy


def test_health_answers_the_questions_with_numbers(admin: Account) -> None:
    body = admin.client.get(f"{ADMIN}/health").json()
    assert body["status"] in ("ok", "warning", "critical") and body["headline"]
    names = [c["name"] for c in body["components"]]
    assert names == [
        "API", "Database", "Migrations", "Workers", "Queue", "Job sources", "Model provider", "Evaluation",
    ]  # fmt: skip
    by = {c["name"]: c for c in body["components"]}
    assert by["Database"]["status"] == "ok" and by["Migrations"]["status"] == "ok"
    assert by["Evaluation"]["status"] == "unknown" and "3.6" in by["Evaluation"]["detail"]
    assert body["version"] and body["environment"]
    assert body["thresholds"]["queue_stale_warning_seconds"] == 300
    assert body["requests"]["window_minutes"] == 15


def test_request_timings_are_measured_by_the_api(admin: Account) -> None:
    for _ in range(3):
        assert admin.client.get(f"{ADMIN}/overview").status_code == 200
    stats = admin.client.get(f"{ADMIN}/health").json()["requests"]
    assert stats["measured"] and stats["requests"] >= 3 and stats["p95_ms"] is not None
    assert stats["server_errors"] == 0


def test_a_dead_letter_and_a_stuck_task_raise_alerts_and_are_listed(
    admin: Account, engine: Engine
) -> None:
    dead = plant_task(engine, "obs.test_dead", "dead_letter", attempts=5, error="gave up")
    stuck = plant_task(
        engine, "obs.test_stuck", "running", locked_until=datetime.now(UTC) - timedelta(minutes=5)
    )
    retry = plant_task(engine, "obs.test_retry", "retry_scheduled", attempts=2, error="busy")
    try:
        body = admin.client.get(f"{ADMIN}/health").json()
        keys = {a["key"] for a in body["alerts"]}
        assert {"dead_letters", "stuck_tasks"} <= keys
        for alert in body["alerts"]:
            assert alert["action"] and alert["runbook"] == "operations/runbooks/alerts.md"
        trouble = {t["id"]: t for t in body["trouble_tasks"]}
        assert trouble[str(stuck)]["state"] == "stuck"
        assert (
            trouble[str(retry)]["state"] == "retrying"
            and trouble[str(retry)]["last_error"] == "busy"
        )
        assert str(dead) not in trouble  # a dead letter has its own list
        assert body["status"] in ("warning", "critical")
    finally:
        cleanup_tasks(engine, dead, stuck, retry)


def test_a_paused_source_is_named_in_the_alerts_and_the_table(
    admin: Account, engine: Engine
) -> None:
    with Session(engine) as db, db.begin():
        key = db.execute(
            text(
                "SELECT key FROM job_sources WHERE compliance_status = 'verified' ORDER BY key LIMIT 1"
            )
        ).scalar_one()
        before = db.execute(
            text(
                "SELECT enabled, failure_streak, breaker_open_until FROM job_sources WHERE key = :k"
            ),
            {"k": key},
        ).one()
        db.execute(
            text(
                "UPDATE job_sources SET enabled = true, failure_streak = 6, "
                "breaker_open_until = now() + interval '10 minutes' WHERE key = :k"
            ),
            {"k": key},
        )
    try:
        body = admin.client.get(f"{ADMIN}/health").json()
        assert f"source_breaker_{key}" in {a["key"] for a in body["alerts"]}
        row = next(s for s in body["sources"] if s["key"] == key)
        assert row["breaker_open"] and row["failure_streak"] == 6 and row["enabled"]
        assert (
            next(c for c in body["components"] if c["name"] == "Job sources")["status"] == "warning"
        )
    finally:
        with Session(engine) as db, db.begin():
            db.execute(
                text(
                    "UPDATE job_sources SET enabled = :e, failure_streak = :f, "
                    "breaker_open_until = :b WHERE key = :k"
                ),
                {"e": before[0], "f": before[1], "b": before[2], "k": key},
            )


def test_security_events_and_rate_limit_pressure_are_counted_without_naming_anyone(
    admin: Account, engine: Engine
) -> None:
    for _ in range(3):
        record_audit(engine, category="security", action="origin_rejected", metadata={"path": "/x"})
    bucket = f"studio_export_user:{uuid.uuid4().hex}"
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO rate_limit_buckets (bucket_key, window_start, hits) "
                "VALUES (:k, now(), 999)"
            ),
            {"k": bucket},
        )
    try:
        body = admin.client.get(f"{ADMIN}/health").json()
        events = {e["action"]: e for e in body["security_24h"]}
        assert events["origin_rejected"]["count"] >= 3
        assert events["origin_rejected"]["label"] == "Requests blocked for their origin"
        limits = {r["policy"]: r["counters_over"] for r in body["rate_limits_24h"]}
        assert limits["studio_export_user"] >= 1
        assert bucket.split(":")[1] not in str(body)  # nobody is named
    finally:
        with Session(engine) as db, db.begin():
            db.execute(text("DELETE FROM rate_limit_buckets WHERE bucket_key = :k"), {"k": bucket})


# ------------------------------------------------------------------------ what does it cost


def test_usage_adds_up_by_model_purpose_and_day(
    admin: Account, make_account: MakeAccount, app: FastAPI, engine: Engine
) -> None:
    other = make_account(app)
    tag = f"m-{uuid.uuid4().hex[:8]}"
    purpose = f"p-{uuid.uuid4().hex[:8]}"
    call(
        engine, None, admin.user_id, model=tag, purpose=purpose, estimated_cost_usd=Decimal("0.010")
    )
    call(engine, None, other.user_id, model=tag, purpose=purpose, estimated_cost_usd=Decimal("0.030"),
         input_tokens=300, output_tokens=40)  # fmt: skip
    call(engine, None, other.user_id, model=tag, purpose=purpose, status="error", error_class="TRANSIENT",
         estimated_cost_usd=Decimal("0"), input_tokens=0, output_tokens=0)  # fmt: skip
    body = admin.client.get(f"{ADMIN}/usage?days=7").json()
    model = next(r for r in body["by_model"] if r["key"] == f"gemini / {tag}")
    assert model["calls"] == 3 and model["errors"] == 1
    assert model["input_tokens"] == 400 and model["output_tokens"] == 60
    assert model["cost_usd"] == pytest.approx(0.04)
    op = next(r for r in body["by_purpose"] if r["key"] == purpose)
    assert op["calls"] == 3
    today = datetime.now(UTC).date().isoformat()
    assert today in [d["key"] for d in body["by_day"]]
    assert [d["key"] for d in body["by_day"]] == sorted(d["key"] for d in body["by_day"])
    assert body["calls"] >= 3 and body["accounts"] >= 2 and body["days"] == 7
    assert 0 < body["highest_account_share"] <= 1
    assert body["by_model"][0]["cost_usd"] >= body["by_model"][-1]["cost_usd"]  # dearest first


def test_usage_never_names_a_person(admin: Account, engine: Engine) -> None:
    call(engine, None, admin.user_id, model=f"m-{uuid.uuid4().hex[:6]}")
    raw = admin.client.get(f"{ADMIN}/usage?days=30").text
    assert admin.email not in raw and admin.user_id not in raw


def test_the_spend_ceiling_raises_an_alert_when_set(
    admin: Account, engine: Engine, app: FastAPI, settings: Any
) -> None:
    assert admin.client.get(f"{ADMIN}/usage").json()["daily_spend_ceiling_usd"] == 0.0
    call(
        engine,
        None,
        admin.user_id,
        model=f"m-{uuid.uuid4().hex[:6]}",
        estimated_cost_usd=Decimal("5"),
    )
    app.state.settings = settings.model_copy(update={"llm_daily_spend_ceiling_usd": 0.01})
    body = admin.client.get(f"{ADMIN}/health").json()
    assert "spend_over_ceiling" in {a["key"] for a in body["alerts"]}
    assert body["status"] == "critical"
    assert admin.client.get(f"{ADMIN}/usage").json()["daily_spend_ceiling_usd"] == 0.01


# ------------------------------------------------------------------------ one run, system tables only


def test_an_admin_can_trace_a_run_from_tasks_and_model_calls_alone(
    admin: Account, make_account: MakeAccount, app: FastAPI, engine: Engine
) -> None:
    person = make_account(app)
    run_id = make_run(engine, person, failed=True)
    task = plant_task(
        engine, "obs.trace", "dead_letter", run_id=run_id, owner=uuid.UUID(person.user_id),
        attempts=3, error="provider busy",
    )  # fmt: skip
    call(engine, run_id, person.user_id, model="trace-model", prompt_version="analyze.v2")
    try:
        body = admin.client.get(f"{ADMIN}/trace/{run_id}").json()
        assert body["found"] and body["run_id"] == str(run_id)
        assert [t["task_type"] for t in body["tasks"]] == ["obs.trace"]
        assert body["tasks"][0]["state"] == "dead_letter" and body["tasks"][0]["attempts"] == 3
        assert body["tasks"][0]["last_error"] == "provider busy"
        assert body["tasks"][0]["owner_email"] == person.email
        assert (
            body["calls"][0]["model"] == "trace-model"
            and body["calls"][0]["prompt_version"] == "analyze.v2"
        )
        # No step, no subject, no run row: those are the person's own tables.
        assert "steps" not in body and "subject" not in str(body)
    finally:
        cleanup_tasks(engine, task)


def test_tracing_an_unknown_run_says_not_found_without_an_error(admin: Account) -> None:
    body = admin.client.get(f"{ADMIN}/trace/{uuid.uuid4()}").json()
    assert body["found"] is False and body["tasks"] == [] and body["calls"] == []


def test_the_console_reads_no_tenant_table(admin: Account, engine: Engine) -> None:
    """The routes run with no tenant set. If any query touched a tenant table, Row Level Security
    would return nothing or fail, so the console works because it never reads one."""
    for path in ("health", "usage", f"trace/{uuid.uuid4()}"):
        assert admin.client.get(f"{ADMIN}/{path}").status_code == 200
    source = Path("packages/persistence/src/pv_persistence/observability.py").read_text(
        encoding="utf-8"
    )
    for table in (
        "workflow_runs",
        "workflow_steps",
        "usage_ledger",
        "user_plans",
        "job_postings",
        "resumes",
    ):
        assert table not in source


# ------------------------------------------------------------------------ the person's own Run Inspector


def test_a_failed_run_explains_itself_with_totals_and_a_page_to_go_to(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    person = make_account(app)
    job_id = str(uuid.uuid4())
    run_id = make_run(engine, person, failed=True, subject=job_id)
    call(engine, run_id, person.user_id, estimated_cost_usd=Decimal("0.004"))
    call(engine, run_id, person.user_id, status="error", error_class="TRANSIENT", model="model-y",
         prompt_version="extract.v2", estimated_cost_usd=Decimal("0"))  # fmt: skip
    detail = person.client.get(f"/api/v1/runs/{run_id}").json()
    assert (
        detail["subject_label"] == "A job" and detail["subject_path"] == f"/opportunities/{job_id}"
    )
    assert detail["failure"]["what"] == "The evidence check could not finish."
    assert (
        "Run the check again" in detail["failure"]["next"] and detail["failure"]["retry_possible"]
    )
    totals = detail["totals"]
    assert totals["steps"] == 2 and totals["steps_failed"] == 1
    assert totals["model_calls"] == 2 and totals["model_calls_failed"] == 1
    assert totals["input_tokens"] == 200 and totals["output_tokens"] == 40
    assert totals["cost_usd"] == pytest.approx(0.004)
    assert totals["models"] == ["gemini / model-x", "gemini / model-y"]
    assert totals["prompt_versions"] == ["extract.v1", "extract.v2"]


def test_steps_show_plain_labels_and_numbers_only(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    person = make_account(app)
    run_id = make_run(engine, person, failed=False)
    steps = person.client.get(f"/api/v1/runs/{run_id}").json()["steps"]
    assert (
        steps[0]["step_label"] == "Gather the jobs" and steps[1]["step_label"] == "Write the file"
    )
    assert steps[0]["counts"] == {"jobs": 7}  # the text and the boolean were not passed on
    assert steps[1]["counts"] == {}


def test_a_run_that_worked_has_no_failure_and_no_subject_when_it_has_none(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    person = make_account(app)
    detail = person.client.get(f"/api/v1/runs/{make_run(engine, person, failed=False)}").json()
    assert detail["failure"] is None and detail["subject_label"] is None
    assert detail["totals"]["model_calls"] == 0 and detail["totals"]["cost_usd"] == 0


def test_another_person_still_cannot_open_a_run(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    alice, bob = make_account(app), make_account(app)
    run_id = make_run(engine, alice, failed=True)
    assert bob.client.get(f"/api/v1/runs/{run_id}").status_code == 404


# ------------------------------------------------------------------------ the check command


def test_the_check_command_prints_each_alert_and_exits_by_severity(
    engine: Engine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    dead = plant_task(engine, "obs.cli", "dead_letter", attempts=5, error="x")
    try:
        code = cli.main(["check-alerts"])
        out = capsys.readouterr().out
        assert "Tasks gave up" in out and "Do: " in out and "[WARNING]" in out
        assert code in (0, 1)
        assert ("[CRITICAL]" in out) == (code == 1)
    finally:
        cleanup_tasks(engine, dead)


def test_the_check_command_exits_1_for_a_critical_alert_and_0_for_none(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import pv_api.services.observability_service as service
    from pv_domain.alerts import Snapshot

    monkeypatch.setattr(
        service, "build_snapshot", lambda engine, stats, now=None: Snapshot(database_ok=False)
    )
    assert cli.main(["check-alerts"]) == 1
    assert "[CRITICAL] The database is not answering" in capsys.readouterr().out
    monkeypatch.setattr(service, "build_snapshot", lambda engine, stats, now=None: Snapshot())
    assert cli.main(["check-alerts"]) == 0
    assert "Nothing needs attention" in capsys.readouterr().out
    monkeypatch.setattr(
        service, "build_snapshot", lambda engine, stats, now=None: Snapshot(stuck_tasks=1)
    )
    assert cli.main(["check-alerts"]) == 0  # a warning alone does not fail the check


@pytest.fixture(autouse=True)
def _tidy() -> Iterator[None]:
    yield
