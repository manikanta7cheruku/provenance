"""Carryover sweep: housekeeping the worker does by itself, plan on model calls, and the label counters.

Against the real database. The shared database holds many test accounts, so these tests assert on
the rows they plant and on counts that moved, never on whole-system totals.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from helpers import Account, promote_to_admin
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_analysis import read_job
from test_observability import cleanup_tasks, plant_task
from test_reports import ask, make_report

from pv_config import Settings
from pv_files import FileStorage
from pv_persistence.llm_usage import record_llm_call
from pv_persistence.observability import feedback_counts, usage_report
from pv_persistence.tenancy import tenant_session
from pv_worker.maintenance import deliver_alerts, run_maintenance, sweep_closed_jobs, sweep_reports

MakeAccount = Callable[..., Account]


class Outbox:
    """A mail server that remembers what it was given, or refuses everything."""

    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = fail

    def send(self, to: str, subject: str, body: str) -> None:
        if self.fail:
            from pv_mail import MailDeliveryError

            raise MailDeliveryError("down", retryable=True)
        self.sent.append((to, subject, body))


# ------------------------------------------------------------------------ expired reports


def test_an_expired_report_and_its_file_are_removed_by_the_sweep_and_a_fresh_one_is_kept(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account = make_account(app)
    old = make_report(account, engine, settings, storage, format="csv")
    fresh = make_report(account, engine, settings, storage, format="csv")
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:
        old_key = db.execute(
            text("SELECT storage_key FROM report_exports WHERE id = :i"), {"i": old["id"]}
        ).scalar_one()
        fresh_key = db.execute(
            text("SELECT storage_key FROM report_exports WHERE id = :i"), {"i": fresh["id"]}
        ).scalar_one()
        db.execute(
            text("UPDATE report_exports SET expires_at = :t WHERE id = :i"),
            {"t": datetime.now(UTC) - timedelta(days=1), "i": old["id"]},
        )
    assert storage.exists(old_key)

    removed, files = sweep_reports(engine, storage)
    assert removed >= 1 and files >= 1
    assert not storage.exists(old_key) and storage.exists(fresh_key)
    with tenant_session(engine, uid) as db:
        ids = {str(r) for r in db.execute(text("SELECT id FROM report_exports")).scalars()}
    assert ids == {fresh["id"]}


def test_the_sweep_never_touches_a_report_still_being_made(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    waiting = ask(account).json()
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:
        db.execute(
            text("UPDATE report_exports SET expires_at = :t"),
            {"t": datetime.now(UTC) - timedelta(days=3)},
        )
    sweep_reports(engine, storage)
    with tenant_session(engine, uid) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM report_exports WHERE id = :i"), {"i": waiting["id"]}
            ).scalar_one()
            == 1
        )


# ------------------------------------------------------------------------ closed listings


def listing(engine: Engine, key: str, closed_days_ago: int | None) -> str:
    external = f"ret-{uuid.uuid4().hex[:10]}"
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO source_jobs (source_key, board_id, external_id, url, title, content_hash, closed_at) "
                "VALUES (:s, 'maint-board', :e, 'https://example.test/j', 'A role', repeat('a', 64), "
                "CASE WHEN CAST(:d AS int) IS NULL THEN NULL ELSE now() - make_interval(days => CAST(:d AS int)) END)"
            ),
            {"s": key, "e": external, "d": closed_days_ago},
        )
    return external


def test_old_closed_listings_are_deleted_and_recent_and_open_ones_are_kept(engine: Engine) -> None:
    with Session(engine) as db:
        key = db.execute(text("SELECT key FROM job_sources ORDER BY key LIMIT 1")).scalar_one()
    old = listing(engine, key, 120)
    recent = listing(engine, key, 10)
    open_ = listing(engine, key, None)
    deleted = sweep_closed_jobs(engine, 90)
    assert deleted >= 1
    with Session(engine) as db:
        left = {
            str(e)
            for e in db.execute(
                text("SELECT external_id FROM source_jobs WHERE external_id = ANY(:l)"),
                {"l": [old, recent, open_]},
            ).scalars()
        }
    assert left == {recent, open_}
    with Session(engine) as db, db.begin():
        db.execute(
            text("DELETE FROM source_jobs WHERE external_id = ANY(:l)"), {"l": [recent, open_]}
        )


# ------------------------------------------------------------------------ alert email


@pytest.fixture
def admin_address(app: FastAPI, make_account: MakeAccount, engine: Engine) -> str:
    account = make_account(app)
    promote_to_admin(engine, account.email)
    return account.email


def test_a_new_alert_is_emailed_to_administrators_once_then_only_after_the_cooldown(
    engine: Engine, settings: Settings, admin_address: str
) -> None:
    stuck = plant_task(
        engine, "maint.stuck", "running", locked_until=datetime.now(UTC) - timedelta(minutes=5)
    )
    on = settings.model_copy(update={"alert_email_enabled": True, "alert_email_cooldown_hours": 24})
    try:
        outbox = Outbox()
        assert deliver_alerts(engine, on, outbox) >= 1
        mine = [m for m in outbox.sent if m[0] == admin_address]
        assert mine and "alert" in mine[0][1] and "outlived their lease" in mine[0][2]
        assert "Do first:" in mine[0][2] and "/admin" in mine[0][2]

        again = Outbox()
        assert (
            deliver_alerts(engine, on, again) == 0 and again.sent == []
        )  # still there, inside the cooldown

        later = Outbox()
        soon = datetime.now(UTC) + timedelta(hours=25)
        assert deliver_alerts(engine, on, later, now=soon) >= 1  # a reminder after the cooldown
        assert any("outlived their lease" in m[2] for m in later.sent)
    finally:
        cleanup_tasks(engine, stuck)

    deliver_alerts(engine, on, Outbox())  # the alert is gone, so its record is cleared
    with Session(engine) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM alert_deliveries WHERE alert_key = 'stuck_tasks'")
            ).scalar_one()
            == 0
        )


def test_a_mail_server_that_is_down_means_the_alert_is_tried_again_not_forgotten(
    engine: Engine, settings: Settings, admin_address: str
) -> None:
    dead = plant_task(
        engine, "maint.stuck2", "running", locked_until=datetime.now(UTC) - timedelta(minutes=5)
    )
    on = settings.model_copy(update={"alert_email_enabled": True})
    try:
        assert deliver_alerts(engine, on, Outbox(fail=True)) == 0
        with Session(engine) as db:
            assert (
                db.execute(
                    text("SELECT count(*) FROM alert_deliveries WHERE alert_key = 'stuck_tasks'")
                ).scalar_one()
                == 0
            )
        ok = Outbox()
        assert deliver_alerts(engine, on, ok) >= 1 and ok.sent
    finally:
        cleanup_tasks(engine, dead)
        deliver_alerts(engine, on, Outbox())


def test_alert_email_is_off_unless_it_is_switched_on(
    engine: Engine, settings: Settings, storage: FileStorage
) -> None:
    dead = plant_task(
        engine, "maint.stuck3", "running", locked_until=datetime.now(UTC) - timedelta(minutes=5)
    )
    try:
        outbox = Outbox()
        done = run_maintenance(
            engine,
            settings.model_copy(update={"alert_email_enabled": False}),
            outbox,
            storage,
            hourly=False,
        )
        assert "alerts_emailed" not in done and outbox.sent == []
        on = run_maintenance(
            engine,
            settings.model_copy(update={"alert_email_enabled": True}),
            Outbox(),
            storage,
            hourly=False,
        )
        assert on["alerts_emailed"] >= 1
    finally:
        cleanup_tasks(engine, dead)
        deliver_alerts(engine, settings.model_copy(update={"alert_email_enabled": True}), Outbox())


def test_a_failing_step_does_not_stop_the_others(
    engine: Engine, settings: Settings, storage: FileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pv_worker.maintenance as module

    def boom(*_a: object, **_k: object) -> int:
        raise RuntimeError("disk")

    monkeypatch.setattr(module, "sweep_reports", boom)
    done = run_maintenance(engine, settings, Outbox(), storage, hourly=True)
    assert "reports_removed" not in done and "closed_jobs_deleted" in done


# ------------------------------------------------------------------------ plan on model calls


def test_a_model_call_records_the_plan_of_the_person_and_cost_adds_up_by_plan(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    paid = make_account(app)
    free = make_account(app)
    tag = f"m-{uuid.uuid4().hex[:6]}"
    with tenant_session(engine, uuid.UUID(paid.user_id)) as db:
        db.execute(
            text(
                "INSERT INTO user_plans (owner_user_id, plan_id, assigned_by) VALUES (:o, 'pro', 'test') ON CONFLICT (owner_user_id) DO UPDATE SET plan_id = 'pro'"
            ),
            {"o": paid.user_id},
        )
    for who, cost in ((paid, "0.020"), (paid, "0.010"), (free, "0.005")):
        record_llm_call(
            engine,
            purpose="x",
            provider="g",
            model=tag,
            input_tokens=1,
            output_tokens=1,
            estimated_cost_usd=Decimal(cost),
            latency_ms=1,
            user_id=uuid.UUID(who.user_id),
        )
    with Session(engine) as db:
        rows = db.execute(
            text("SELECT plan_id, count(*) FROM llm_calls WHERE model = :m GROUP BY plan_id"),
            {"m": tag},
        ).all()
        report = usage_report(db, 7)
    assert {(r[0], r[1]) for r in rows} == {("pro", 2), (None, 1)}
    by_plan = {r.key: r for r in report.by_plan}
    assert "pro" in by_plan and "default plan" in by_plan
    assert by_plan["pro"].cost_usd >= 0.03


def test_a_call_with_no_person_has_no_plan(engine: Engine) -> None:
    tag = f"m-{uuid.uuid4().hex[:6]}"
    record_llm_call(
        engine,
        purpose="x",
        provider="g",
        model=tag,
        input_tokens=1,
        output_tokens=1,
        estimated_cost_usd=Decimal(0),
        latency_ms=1,
    )
    with Session(engine) as db:
        assert (
            db.execute(
                text("SELECT plan_id FROM llm_calls WHERE model = :m"), {"m": tag}
            ).scalar_one()
            is None
        )


# ------------------------------------------------------------------------ the label counters


def add_label(engine: Engine, account: Account, job_id: str) -> uuid.UUID:
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:
        return uuid.UUID(
            str(
                db.execute(
                    text(
                        "INSERT INTO verdict_feedback (owner_user_id, posting_id, subject, shown, answer, scoring_version) "
                        "VALUES (:o, :p, 'recommendation', 'strong', 'right', 'scoring-1') RETURNING id"
                    ),
                    {"o": uid, "p": job_id},
                ).scalar_one()
            )
        )


def test_labels_and_people_are_counted_by_triggers_without_reading_anyone_s_labels(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    person = make_account(app)
    job = read_job(engine, settings, person)
    with Session(engine) as db:
        before = feedback_counts(db)
    first = add_label(engine, person, job)
    add_label(engine, person, job)
    with Session(engine) as db:
        mid = feedback_counts(db)
    assert (
        mid.labels == before.labels + 2 and mid.people == before.people + 1
    )  # two labels, one new person
    with tenant_session(engine, uuid.UUID(person.user_id)) as db:
        db.execute(text("DELETE FROM verdict_feedback WHERE id = :i"), {"i": first})
    with Session(engine) as db:
        assert feedback_counts(db).labels == mid.labels - 1


def test_the_counters_cannot_be_changed_by_the_application(engine: Engine) -> None:
    for statement in (
        "UPDATE feedback_totals SET labels = 999999 WHERE id = 1",
        "INSERT INTO feedback_people (user_id) VALUES (gen_random_uuid())",
        "DELETE FROM feedback_people",
    ):
        with pytest.raises(DBAPIError), Session(engine) as db, db.begin():
            db.execute(text(statement))


def test_deleting_a_person_removes_them_from_the_count_of_people(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    from test_account import ask_delete, deletion_context

    from pv_worker.handlers.delete_account import run_delete

    person = make_account(app)
    job = read_job(engine, settings, person)
    add_label(engine, person, job)
    with Session(engine) as db:
        before = feedback_counts(db)
    ask_delete(person)
    run_delete(deletion_context(engine, settings, person.user_id), storage=storage)
    with Session(engine) as db:
        after = feedback_counts(db)
    assert after.people == before.people - 1 and after.labels == before.labels - 1


def test_the_evaluation_list_says_why_a_learned_ranker_is_not_adopted(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    admin = make_account(app)
    promote_to_admin(engine, admin.email)
    body = admin.client.get("/api/v1/admin/evaluation").json()
    ranker = body["ranker"]
    assert ranker["adopt"] is False and ranker["labels"] >= 0 and ranker["people"] >= 0
    assert any("labels" in reason for reason in ranker["reasons"])
    assert any("No candidate" in reason for reason in ranker["reasons"])
    usage = admin.client.get("/api/v1/admin/usage").json()
    assert "by_plan" in usage and all(
        {"key", "calls", "cost_usd"} <= set(r) for r in usage["by_plan"]
    )
