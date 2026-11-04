"""Checkpoint 2.10: the shortlist email. A schedule of the person's own, a deterministic selection, a
send that cannot repeat, and an email that never reaches an unverified address."""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from test_tailoring import checked_job

from pv_config import Settings
from pv_mail import MailDeliveryError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.send_shortlist import run_send

SHORTLIST = "/api/v1/shortlist"
JOBS = "/api/v1/jobs"
MakeAccount = Callable[..., Account]
WEEKLY = {
    "enabled": True,
    "frequency": "weekly",
    "weekday": 0,
    "hour": 8,
    "timezone": "Asia/Kolkata",
    "max_items": 5,
}


class Outbox:
    """Stands in for the mail server. Records what was sent, or fails as told."""

    def __init__(self, fail: MailDeliveryError | None = None) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = fail

    def send(self, to: str, subject: str, body: str) -> None:
        if self.fail:
            raise self.fail
        self.sent.append((to, subject, body))


def verify(engine: Engine, account: Account, on: bool = True) -> None:
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "UPDATE users SET email_verified_at = CASE WHEN :on THEN now() ELSE NULL END WHERE id = :u"
            ),
            {"on": on, "u": account.user_id},
        )


def configure(account: Account, **changes: Any) -> Any:
    return account.client.put(SHORTLIST, json={**WEEKLY, **changes}, headers=account.csrf)


def settings_row(engine: Engine, account: Account) -> Any:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        return db.execute(text("SELECT * FROM shortlist_settings")).one()


def waiting(engine: Engine, account: Account) -> list[Any]:
    with Session(engine) as db:
        return list(
            db.execute(
                text(
                    "SELECT id, state, run_after, payload FROM tasks WHERE task_type = 'send_shortlist' AND owner_user_id = :u ORDER BY created_at"
                ),
                {"u": account.user_id},
            )
        )


def live(engine: Engine, account: Account) -> list[Any]:
    return [t for t in waiting(engine, account) if t.state in ("queued", "retry_scheduled")]


def later(engine: Engine, account: Account, slot: datetime) -> list[Any]:
    """Tasks waiting for a time after `slot`: what a send arranges as the next one."""
    return [x for x in live(engine, account) if x.run_after > slot + timedelta(minutes=1)]


def ctx(
    engine: Engine,
    settings: Settings,
    account: Account,
    slot: datetime,
    outbox: Outbox,
    *,
    manual: bool = False,
    attempt: int = 1,
) -> TaskContext:
    return TaskContext(
        task_id=uuid.uuid4(), task_type="send_shortlist", args={"slot": slot.isoformat(), "manual": manual}, secret={},
        attempt=attempt, max_attempts=4, owner_user_id=uuid.UUID(account.user_id), run_id=None,
        settings=settings.model_copy(update={"public_base_url": "https://app.example.com"}), engine=engine,
        mailer=outbox,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def runs(engine: Engine, account: Account) -> list[Any]:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        return list(
            db.execute(
                text(
                    "SELECT outcome, item_count, manual, slot FROM shortlist_runs ORDER BY created_at"
                )
            )
        )


@pytest.fixture
def ready(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> tuple[Account, str]:
    account, job_id = checked_job(app, make_account, engine, settings)
    verify(engine, account)
    return account, job_id


def band_of(account: Account, job_id: str) -> str:
    return str(account.client.get(f"{JOBS}/{job_id}/analysis").json()["score"]["band"])


# --------------------------------------------------------------------- the schedule


def test_it_is_off_by_default_and_says_what_it_would_need(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    body = account.client.get(SHORTLIST).json()
    assert body["settings"]["enabled"] is False and body["settings"]["next_run_at"] is None
    assert body["settings"]["schedule_text"] == "Every Monday at 08:00 (UTC)"
    assert body["email_verified"] is False and "Verify your email" in body["blocker"]
    assert body["runs"] == [] and body["delivery_note"]


def test_it_cannot_be_turned_on_for_an_unverified_address(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    refused = configure(account)
    assert refused.status_code == 409 and refused.json()["code"] == "EMAIL_NOT_VERIFIED"
    assert waiting(engine, account) == []
    assert (
        configure(account, enabled=False).status_code == 200
    )  # settings can still be kept while off


def test_turning_it_on_works_out_the_next_time_on_the_persons_clock_and_queues_it(
    ready: tuple[Account, str], engine: Engine
) -> None:
    account, _ = ready
    body = configure(account).json()
    nxt = datetime.fromisoformat(body["settings"]["next_run_at"])
    assert nxt > datetime.now(UTC) and nxt - datetime.now(UTC) <= timedelta(days=8)
    assert (nxt.hour, nxt.minute, nxt.weekday()) == (
        2,
        30,
        0,
    ) or nxt.weekday() == 6  # Monday 08:00 in Kolkata
    assert body["settings"]["schedule_text"] == "Every Monday at 08:00 (Asia/Kolkata)"
    (task,) = live(engine, account)
    assert (
        abs(task.run_after - nxt) < timedelta(seconds=5)
        and json.loads(json.dumps(task.payload))["args"]["manual"] is False
    )
    assert account.email not in json.dumps(
        task.payload
    )  # the address is read at send time, never stored in a task


def test_changing_the_schedule_replaces_what_is_waiting_and_turning_it_off_cancels_it(
    ready: tuple[Account, str], engine: Engine
) -> None:
    account, _ = ready
    configure(account)
    configure(account, frequency="daily", hour=18)
    assert len(live(engine, account)) == 1
    assert sum(1 for t in waiting(engine, account) if t.state == "cancelled") == 1
    off = configure(account, enabled=False).json()
    assert off["settings"]["enabled"] is False and off["settings"]["next_run_at"] is None
    assert live(engine, account) == []


def test_saving_the_same_schedule_twice_leaves_one_task(
    ready: tuple[Account, str], engine: Engine
) -> None:
    account, _ = ready
    configure(account)
    configure(account)
    assert len(live(engine, account)) == 1


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"timezone": "Mars/Base"}, "timezone"),
        ({"timezone": "../../etc/passwd"}, "timezone"),
        ({"hour": 24}, "hour"),
        ({"frequency": "hourly"}, "frequency"),
        ({"max_items": 11}, "max_items"),
        ({"weekday": 9}, "weekday"),
    ],
)
def test_bad_settings_are_refused_with_the_field(
    ready: tuple[Account, str], changes: dict[str, Any], field: str
) -> None:
    account, _ = ready
    response = configure(account, **changes)
    assert response.status_code == 422


def test_extra_fields_are_refused(ready: tuple[Account, str]) -> None:
    account, _ = ready
    assert (
        account.client.put(
            SHORTLIST, json={**WEEKLY, "owner_user_id": str(uuid.uuid4())}, headers=account.csrf
        ).status_code
        == 422
    )


# --------------------------------------------------------------------- what is picked


def test_the_preview_is_what_an_email_would_hold(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    band = band_of(account, job_id)
    preview = account.client.get(f"{SHORTLIST}/preview").json()
    if band in ("strong", "good"):
        (item,) = preview["items"]
        assert item["id"] == job_id and item["band"] == band
        assert item["reason"].startswith("Strong match:" if band == "strong" else "Good match:")
        assert "required requirement" in item["reason"]
    else:
        assert preview["items"] == [] and "Nothing would be sent" in preview["note"]


def test_a_dismissed_or_applied_job_is_not_picked_and_a_brought_back_one_is(
    ready: tuple[Account, str],
) -> None:
    account, job_id = ready
    if band_of(account, job_id) not in ("strong", "good"):
        pytest.skip("the sample job is not a good fit for this profile")
    count = lambda: len(account.client.get(f"{SHORTLIST}/preview").json()["items"])  # noqa: E731
    assert count() == 1
    account.client.post(
        f"{JOBS}/{job_id}/decision", json={"action": "dismiss"}, headers=account.csrf
    )
    assert count() == 0
    account.client.post(
        f"{JOBS}/{job_id}/decision", json={"action": "undo_dismiss"}, headers=account.csrf
    )
    assert count() == 1
    account.client.post(
        f"{JOBS}/{job_id}/decision", json={"action": "mark_applied"}, headers=account.csrf
    )
    assert count() == 0


def test_a_job_that_has_not_been_checked_is_never_picked(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    verify(engine, account)
    account.client.post(
        f"{JOBS}/manual", json={"title": "Engineer", "description": "x" * 150}, headers=account.csrf
    )
    assert account.client.get(f"{SHORTLIST}/preview").json()["items"] == []


# --------------------------------------------------------------------- sending


def due(engine: Engine, account: Account) -> datetime:
    return settings_row(engine, account).next_run_at


def test_the_send_goes_to_the_verified_address_with_each_jobs_reason_and_arranges_the_next(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    if band_of(account, job_id) not in ("strong", "good"):
        pytest.skip("the sample job is not a good fit for this profile")
    configure(account)
    slot = due(engine, account)
    outbox = Outbox()
    run_send(ctx(engine, settings, account, slot, outbox))
    ((to, subject, body),) = outbox.sent
    assert to == account.email and subject == "Your Provenance shortlist: 1 job worth a look"
    assert f"https://app.example.com/opportunities/{job_id}" in body and "match:" in body
    assert (
        "Every Monday at 08:00 (Asia/Kolkata)" in body
        and "https://app.example.com/settings" in body
    )
    assert "does not apply for you" in body
    (run,) = runs(engine, account)
    assert (run.outcome, run.item_count, run.manual) == ("sent", 1, False)
    row = settings_row(engine, account)
    assert row.next_run_at > slot and row.last_run_at is not None
    (following,) = later(engine, account, slot)
    assert abs(following.run_after - row.next_run_at) < timedelta(seconds=5)


def test_a_retried_or_repeated_task_for_the_same_time_sends_nothing_twice(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    if band_of(account, job_id) not in ("strong", "good"):
        pytest.skip("the sample job is not a good fit for this profile")
    configure(account)
    slot = due(engine, account)
    outbox = Outbox()
    run_send(ctx(engine, settings, account, slot, outbox))
    run_send(
        ctx(engine, settings, account, slot, outbox)
    )  # the schedule moved on: this time is stale
    # The task died after recording the run but before arranging the next one:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        db.execute(text("UPDATE shortlist_settings SET next_run_at = :s"), {"s": slot})
    run_send(ctx(engine, settings, account, slot, outbox))
    assert len(outbox.sent) == 1 and len(runs(engine, account)) == 1
    assert settings_row(engine, account).next_run_at > slot  # the next one was still arranged


def test_a_job_that_was_sent_is_not_sent_again_and_an_empty_week_sends_no_email(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    if band_of(account, job_id) not in ("strong", "good"):
        pytest.skip("the sample job is not a good fit for this profile")
    configure(account)
    outbox = Outbox()
    run_send(ctx(engine, settings, account, due(engine, account), outbox))
    run_send(ctx(engine, settings, account, due(engine, account), outbox))
    assert len(outbox.sent) == 1
    assert [r.outcome for r in runs(engine, account)] == ["sent", "nothing"]
    shown = account.client.get(SHORTLIST).json()["runs"]
    assert [r["outcome"] for r in shown] == ["nothing", "sent"] and "Nothing to send" in shown[0][
        "outcome_text"
    ]


def test_an_address_that_is_not_verified_when_the_time_comes_gets_nothing(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, _ = ready
    configure(account)
    verify(engine, account, False)
    outbox = Outbox()
    due_before = due(engine, account)
    run_send(ctx(engine, settings, account, due_before, outbox))
    assert outbox.sent == [] and [r.outcome for r in runs(engine, account)] == ["skipped"]
    assert (
        len(later(engine, account, due_before)) == 1
    )  # still scheduled: verifying later makes it work


def test_a_task_for_a_time_that_is_no_longer_the_next_one_does_nothing(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, _ = ready
    configure(account)
    old = due(engine, account)
    configure(account, hour=20)  # the schedule changed
    outbox = Outbox()
    run_send(ctx(engine, settings, account, old, outbox))
    configure(account, enabled=False)
    run_send(
        ctx(
            engine, settings, account, due(engine, account) if due(engine, account) else old, outbox
        )
    )
    assert outbox.sent == [] and runs(engine, account) == []


def test_mail_trouble_is_retried_and_then_recorded_without_ending_the_email(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    if band_of(account, job_id) not in ("strong", "good"):
        pytest.skip("the sample job is not a good fit for this profile")
    configure(account)
    slot = due(engine, account)
    broken = Outbox(MailDeliveryError("The mail server is busy.", retryable=True))
    with pytest.raises(TaskFailure):
        run_send(ctx(engine, settings, account, slot, broken, attempt=1))
    assert runs(engine, account) == []
    run_send(ctx(engine, settings, account, slot, broken, attempt=4))
    assert [r.outcome for r in runs(engine, account)] == ["failed"]
    assert (
        settings_row(engine, account).next_run_at > slot and len(later(engine, account, slot)) == 1
    )
    with tenant_session(
        engine, uuid.UUID(account.user_id)
    ) as db:  # a failed run does not use the job up
        assert db.execute(text("SELECT count(*) FROM shortlist_items")).scalar_one() == 0


def test_the_next_time_is_worked_from_now_so_a_late_worker_does_not_send_a_pile(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, _ = ready
    configure(account, frequency="daily")
    long_ago = datetime.now(UTC) - timedelta(days=30)
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        db.execute(text("UPDATE shortlist_settings SET next_run_at = :s"), {"s": long_ago})
    run_send(ctx(engine, settings, account, long_ago, Outbox()))
    assert settings_row(engine, account).next_run_at > datetime.now(UTC)


# --------------------------------------------------------------------- send one now


def test_send_one_now_needs_a_verified_address_and_queues_a_manual_send(
    app: FastAPI,
    make_account: MakeAccount,
    ready: tuple[Account, str],
    engine: Engine,
    settings: Settings,
) -> None:
    stranger = make_account(app)
    assert stranger.client.post(f"{SHORTLIST}/send", headers=stranger.csrf).status_code == 409
    account, job_id = ready
    queued = account.client.post(f"{SHORTLIST}/send", headers=account.csrf)
    assert queued.status_code == 202 and queued.json()["queued"] is True
    (task,) = live(engine, account)
    args = task.payload["args"]
    assert args["manual"] is True
    outbox = Outbox()
    run_send(
        ctx(engine, settings, account, datetime.fromisoformat(args["slot"]), outbox, manual=True)
    )
    (run,) = runs(engine, account)
    assert run.manual is True
    if band_of(account, job_id) in ("strong", "good"):
        assert run.outcome == "sent" and len(outbox.sent) == 1
    assert [
        x for x in live(engine, account) if not x.payload["args"]["manual"]
    ] == []  # a manual send arranges nothing further


# --------------------------------------------------------------------- privacy


def test_settings_runs_and_previews_belong_to_their_owner(
    app: FastAPI,
    make_account: MakeAccount,
    ready: tuple[Account, str],
    engine: Engine,
    settings: Settings,
) -> None:
    owner, job_id = ready
    configure(owner)
    run_send(ctx(engine, settings, owner, due(engine, owner), Outbox()))
    other = make_account(app)
    verify(engine, other)
    seen = other.client.get(SHORTLIST).json()
    assert seen["runs"] == [] and seen["settings"]["enabled"] is False
    assert other.client.get(f"{SHORTLIST}/preview").json()["items"] == []
    with tenant_session(engine, uuid.UUID(other.user_id)) as db:
        for table in ("shortlist_settings", "shortlist_runs", "shortlist_items"):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0  # noqa: S608


def test_deleting_a_job_removes_it_from_the_history(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    if band_of(account, job_id) not in ("strong", "good"):
        pytest.skip("the sample job is not a good fit for this profile")
    configure(account)
    run_send(ctx(engine, settings, account, due(engine, account), Outbox()))
    account.client.delete(f"{JOBS}/{job_id}", headers=account.csrf)
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        assert db.execute(text("SELECT count(*) FROM shortlist_items")).scalar_one() == 0


def test_the_shortlist_needs_a_signed_in_writer(ready: tuple[Account, str]) -> None:
    account, _ = ready
    assert account.client.put(SHORTLIST, json=WEEKLY).status_code in (401, 403)
    account.client.cookies.clear()
    assert account.client.get(SHORTLIST).status_code == 401
    assert account.client.post(f"{SHORTLIST}/send", headers=account.csrf).status_code == 401


def test_changes_are_audited_without_the_address_or_any_job(
    ready: tuple[Account, str], engine: Engine
) -> None:
    account, _ = ready
    configure(account)
    account.client.post(f"{SHORTLIST}/send", headers=account.csrf)
    with Session(engine) as db:
        rows = list(
            db.execute(
                text(
                    "SELECT action, metadata FROM audit_events WHERE actor_user_id = :u AND action LIKE 'shortlist.%' ORDER BY created_at"
                ),
                {"u": account.user_id},
            )
        )
    assert [r.action for r in rows] == ["shortlist.settings_changed", "shortlist.send_requested"]
    assert account.email not in json.dumps([r.metadata for r in rows])
