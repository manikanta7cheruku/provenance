"""Checkpoint 3.3: plans, quotas and the usage ledger with the real database. What is metered, what is
not, the structured refusal, the same event charged once, plans as data, and ownership."""

import json
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session
from test_analysis import read_job
from test_analysis import start as start_analysis
from test_tailoring import checked_job

from pv_config import Settings
from pv_persistence.engine import create_db_engine
from pv_persistence.entitlements import assign_plan
from pv_persistence.tenancy import tenant_session

PLAN = "/api/v1/plan"
JOBS = "/api/v1/jobs"
MakeAccount = Callable[..., Account]

TINY = {
    "units": {"discovery_run": 1, "job_analysis": 1, "url_analysis": 1, "material_generation": 2},
    "resumes": 2,
    "exports_per_resume": 3,
}


@pytest.fixture
def owner_engine(settings: Settings) -> Iterator[Engine]:
    """The database owner. Only the owner can change a plan, so tests that need a small one use it."""
    owner = create_db_engine(settings.migration_database_url.get_secret_value())
    yield owner
    owner.dispose()


@pytest.fixture
def tiny_plan(owner_engine: Engine) -> Iterator[str]:
    plan_id = f"tiny_{uuid.uuid4().hex[:8]}"
    with Session(owner_engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO plans (id, label, sort_order, data) VALUES (:i, 'Tiny', 99, CAST(:d AS jsonb))"
            ),
            {"i": plan_id, "d": json.dumps(TINY)},
        )
    yield plan_id
    with Session(owner_engine) as db, db.begin():
        db.execute(text("DELETE FROM user_plans WHERE plan_id = :i"), {"i": plan_id})
        db.execute(text("DELETE FROM plans WHERE id = :i"), {"i": plan_id})


def put_on(engine: Engine, account: Account, plan_id: str) -> None:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        assign_plan(db, uuid.UUID(account.user_id), plan_id, "test")


def plan(account: Account) -> dict[str, Any]:
    response = account.client.get(PLAN)
    assert response.status_code == 200, response.text
    return dict(response.json())


def quota(body: dict[str, Any], unit: str) -> dict[str, Any]:
    return next(q for q in body["quotas"] if q["unit"] == unit)


def ledger(engine: Engine, account: Account) -> list[Any]:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        return list(
            db.execute(
                text(
                    "SELECT unit, event_key, plan_id, amount FROM usage_ledger ORDER BY created_at"
                )
            ).all()
        )


# --------------------------------------------------------------------- the schema


def test_the_tables_have_forced_security_and_the_plans_are_read_only_to_the_application(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    uid = uuid.UUID(account.user_id)
    with Session(engine) as db:
        flags = db.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('user_plans', 'usage_ledger')"
            )
        ).all()
        seeded = db.execute(text("SELECT id FROM plans ORDER BY sort_order")).scalars().all()
    assert len(flags) == 2 and all(f[1] and f[2] for f in flags)
    assert [p for p in seeded if p in ("free", "starter", "pro")] == ["free", "starter", "pro"]
    for statement in (
        "INSERT INTO plans (id, label) VALUES ('hack', 'Hack')",
        "UPDATE plans SET data = '{}'::jsonb",
        "DELETE FROM plans",
    ):
        with pytest.raises(ProgrammingError), Session(engine) as db, db.begin():
            db.execute(text(statement))
    insert = "INSERT INTO usage_ledger (owner_user_id, unit, period_start, event_key, plan_id) VALUES (:u, :unit, '2026-11-01', :k, 'free')"
    with tenant_session(engine, uid) as db:
        db.execute(text(insert), {"u": str(uid), "unit": "job_analysis", "k": "a"})
    with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:  # the same event twice
        db.execute(text(insert), {"u": str(uid), "unit": "job_analysis", "k": "a"})
    with (
        pytest.raises(DBAPIError),
        tenant_session(engine, uid) as db,
    ):  # a unit that is not billable
        db.execute(text(insert), {"u": str(uid), "unit": "free_lunch", "k": "b"})


# --------------------------------------------------------------------- reading the plan


def test_a_new_person_is_on_the_free_plan_with_nothing_used(
    app: FastAPI, make_account: MakeAccount
) -> None:
    body = plan(make_account(app))
    assert (
        body["plan_id"] == "free" and body["plan_label"] == "Free" and body["provisional"] is True
    )
    assert [q["unit"] for q in body["quotas"]] == [
        "discovery_run",
        "job_analysis",
        "url_analysis",
        "material_generation",
    ]
    assert quota(body, "job_analysis")["limit"] == 30 and quota(body, "job_analysis")["used"] == 0
    assert (
        quota(body, "job_analysis")["remaining"] == 30
        and quota(body, "job_analysis")["state"] == "ok"
    )
    assert (
        body["resumes_limit"] == 1 and body["resumes_used"] == 0 and body["exports_per_resume"] == 5
    )
    assert body["recent"] == []
    assert body["resets_at"] > f"{body['period_start']}"
    assert [p["id"] for p in body["plans"] if p["current"]] == ["free"]


def test_payments_are_off_and_changing_plan_changes_nothing(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    body = plan(account)
    assert (
        body["payments"]["enabled"] is False and "Nothing is charged" in body["payments"]["message"]
    )
    response = account.client.post(f"{PLAN}/upgrade", json={"plan_id": "pro"}, headers=account.csrf)
    assert response.status_code == 409 and response.json()["code"] == "PAYMENTS_NOT_AVAILABLE"
    assert plan(account)["plan_id"] == "free"


def test_the_plan_needs_a_signed_in_person(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    assert account.client.post(f"{PLAN}/upgrade", json={"plan_id": "pro"}).status_code in {
        400,
        401,
        403,
    }
    account.client.cookies.clear()
    assert account.client.get(PLAN).status_code == 401


def test_one_person_cannot_see_anothers_usage_or_plan(
    app: FastAPI, make_account: MakeAccount, engine: Engine, tiny_plan: str
) -> None:
    mine, theirs = make_account(app), make_account(app)
    put_on(engine, mine, tiny_plan)
    assert plan(mine)["plan_id"] == tiny_plan and plan(theirs)["plan_id"] == "free"
    with tenant_session(engine, uuid.UUID(theirs.user_id)) as db:
        assert db.execute(text("SELECT count(*) FROM user_plans")).scalar_one() == 0


# --------------------------------------------------------------------- metering


def test_checking_a_job_uses_one_unit_and_checking_it_again_in_the_month_is_free(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account, job_id = checked_job(app, make_account, engine, settings)
    body = plan(account)
    assert quota(body, "job_analysis")["used"] == 1
    assert [r.unit for r in ledger(engine, account)] == ["job_analysis"]
    assert (
        ledger(engine, account)[0].event_key == f"job_analysis:{job_id}"
        and ledger(engine, account)[0].plan_id == "free"
    )
    assert body["recent"][0]["label"] == "Job evidence checks"
    # Starting again for the same job in the same month is the same event.
    start_analysis(account, job_id)
    assert quota(plan(account), "job_analysis")["used"] == 1


def test_the_quota_refuses_with_a_structured_error_and_nothing_is_started(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, tiny_plan: str
) -> None:
    account, first = checked_job(app, make_account, engine, settings)  # one unit used
    second = read_job(engine, settings, account, "contract_with_preferred")
    put_on(engine, account, tiny_plan)  # one check a month
    refused = start_analysis(account, second)
    assert refused.status_code == 429, refused.text
    body = refused.json()
    assert body["code"] == "QUOTA_EXCEEDED" and body["failure_class"] == "QUOTA_EXCEEDED"
    assert "1 of the 1 checks" in body["message"] and "Tiny plan" in body["message"]
    assert "Nothing was changed" in body["message"]
    details = body["details"]
    assert details["unit"] == "job_analysis" and details["used"] == 1 and details["limit"] == 1
    assert details["plan"] == tiny_plan
    assert details["resets_at"].endswith("+00:00") and details["resets_at"][8:10] == "01"
    # Nothing was charged and nothing was queued for the refused request.
    assert quota(plan(account), "job_analysis")["used"] == 1
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        queued = db.execute(
            text(
                "SELECT count(*) FROM tasks WHERE task_type = 'analyze_job' AND payload::text LIKE :p"
            ),
            {"p": f"%{second}%"},
        ).scalar_one()
    assert queued == 0
    # The job already checked this month can still be checked again: it is the same event.
    assert start_analysis(account, first).status_code != 429


def test_reading_is_never_metered_even_when_the_quota_is_used_up(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, tiny_plan: str
) -> None:
    account, job_id = checked_job(app, make_account, engine, settings)
    put_on(engine, account, tiny_plan)
    assert quota(plan(account), "job_analysis")["state"] == "reached"
    for path in (
        f"{JOBS}/{job_id}",
        f"{JOBS}/{job_id}/analysis",
        f"{JOBS}/{job_id}/drafts",
        f"{JOBS}/{job_id}/preparation",
        "/api/v1/profile/entries",
        "/api/v1/studio/resumes",
    ):
        assert account.client.get(path).status_code == 200, path
    assert quota(plan(account), "job_analysis")["used"] == 1


def test_each_generation_of_material_is_its_own_unit_and_the_limit_stops_the_next(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, tiny_plan: str
) -> None:
    account, job_id = checked_job(app, make_account, engine, settings)
    put_on(engine, account, tiny_plan)  # two pieces of material a month
    prep = f"{JOBS}/{job_id}/preparation/outputs"
    assert account.client.post(f"{prep}/questions", headers=account.csrf).status_code == 202
    assert account.client.post(f"{prep}/behavioral", headers=account.csrf).status_code == 202
    third = account.client.post(f"{prep}/technical", headers=account.csrf)
    assert third.status_code == 429 and third.json()["details"]["unit"] == "material_generation"
    assert quota(plan(account), "material_generation")["used"] == 2
    drafts = account.client.post(
        f"{JOBS}/{job_id}/drafts", json={"kind": "cover_note", "question": ""}, headers=account.csrf
    )
    assert drafts.status_code == 429  # drafts share the same unit
    assert [r.unit for r in ledger(engine, account)].count("material_generation") == 2


def test_a_refused_request_leaves_no_half_written_work(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, tiny_plan: str
) -> None:
    account, job_id = checked_job(app, make_account, engine, settings)
    put_on(engine, account, tiny_plan)
    prep = f"{JOBS}/{job_id}/preparation/outputs"
    account.client.post(f"{prep}/questions", headers=account.csrf)
    account.client.post(f"{prep}/behavioral", headers=account.csrf)
    account.client.post(f"{prep}/technical", headers=account.csrf)
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        actions = (
            db.execute(text("SELECT action FROM prep_outputs ORDER BY action")).scalars().all()
        )
    assert actions == ["behavioral", "questions"]


def test_the_plan_decides_how_many_resumes_are_kept(
    app: FastAPI, make_account: MakeAccount, engine: Engine, tiny_plan: str
) -> None:
    account = make_account(app)
    body = {"start": "blank", "template": "classic"}
    assert (
        account.client.post("/api/v1/studio/resumes", json=body, headers=account.csrf).status_code
        == 201
    )
    free = account.client.post("/api/v1/studio/resumes", json=body, headers=account.csrf)
    assert free.status_code == 409 and free.json()["code"] == "RESUME_LIMIT"
    assert (
        free.json()["message"] == "The Free plan keeps 1 resume. Delete one first to start another."
    )
    assert account.client.get("/api/v1/studio/options").json()["max_resumes"] == 1
    put_on(engine, account, tiny_plan)
    assert account.client.get("/api/v1/studio/options").json()["max_resumes"] == 2
    assert (
        account.client.post("/api/v1/studio/resumes", json=body, headers=account.csrf).status_code
        == 201
    )
    third = account.client.post("/api/v1/studio/resumes", json=body, headers=account.csrf)
    assert third.status_code == 409 and "Tiny plan keeps 2 resumes" in third.json()["message"]
    assert plan(account)["resumes_used"] == 2 and plan(account)["resumes_limit"] == 2


def test_two_requests_at_once_cannot_both_take_the_last_unit(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, tiny_plan: str
) -> None:
    import threading

    from pv_api.errors import ApiError
    from pv_api.services import entitlement_service

    account = make_account(app)
    put_on(engine, account, tiny_plan)
    uid = uuid.UUID(account.user_id)
    outcomes: list[str] = []

    def take(key: str) -> None:
        try:
            with tenant_session(engine, uid) as db:
                entitlement_service.charge(db, settings, uid, "job_analysis", key)
            outcomes.append("ok")
        except ApiError:
            outcomes.append("refused")

    threads = [threading.Thread(target=take, args=(f"race:{i}",)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["ok"] + ["refused"] * 5
    assert quota(plan(account), "job_analysis")["used"] == 1


# --------------------------------------------------------------------- plans as data


def test_a_plan_removed_or_broken_can_only_be_stricter(
    app: FastAPI, make_account: MakeAccount, engine: Engine, owner_engine: Engine, tiny_plan: str
) -> None:
    account = make_account(app)
    put_on(engine, account, tiny_plan)
    with Session(owner_engine) as db, db.begin():
        db.execute(
            text("UPDATE plans SET data = CAST(:d AS jsonb) WHERE id = :i"),
            {"d": json.dumps({"units": {"job_analysis": "plenty"}}), "i": tiny_plan},
        )
    body = plan(account)
    assert (
        quota(body, "job_analysis")["limit"] == 0
        and quota(body, "job_analysis")["state"] == "reached"
    )
    assert body["resumes_limit"] == 0
    with Session(owner_engine) as db, db.begin():
        db.execute(text("UPDATE plans SET active = false WHERE id = :i"), {"i": tiny_plan})
    assert plan(account)["plan_id"] == "free"  # a switched off plan falls back to the default


def test_the_operator_command_sets_and_shows_a_plan(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    capsys: pytest.CaptureFixture[str],
    tiny_plan: str,
) -> None:
    from pv_api.cli import main

    account = make_account(app)
    assert main(["set-plan", "--email", account.email, "--plan", tiny_plan]) == 0
    assert plan(account)["plan_id"] == tiny_plan
    assert main(["set-plan", "--email", account.email, "--plan", "nonsense"]) == 1
    assert main(["set-plan", "--email", "nobody@example.com", "--plan", "pro"]) == 1
    capsys.readouterr()
    assert main(["show-plan", "--email", account.email]) == 0
    shown = capsys.readouterr().out
    assert "Tiny plan" in shown and "job_analysis: 0 of 1" in shown
    with Session(engine) as db:
        actions = db.execute(
            text(
                "SELECT metadata::text FROM audit_events WHERE action = 'admin.plan_set' ORDER BY created_at DESC LIMIT 1"
            )
        ).scalar_one()
    assert tiny_plan in actions


def test_leaving_removes_the_ledger_with_the_person(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)
    with Session(engine) as db, db.begin():
        db.execute(text("DELETE FROM users WHERE id = :u"), {"u": account.user_id})
    with Session(engine) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM usage_ledger WHERE owner_user_id = :u"),
                {"u": account.user_id},
            ).scalar_one()
            == 0
        )
