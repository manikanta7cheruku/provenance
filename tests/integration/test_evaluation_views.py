"""Checkpoint 3.6: stored evaluation runs and the admin views over them, against the real database.

evaluation_runs is append-only for the application role (a stored result is a record), so these
tests cannot clean up after themselves. Each one that stores a failing run stores a passing run
after it, so the newest run of a suite is left healthy for whatever runs next.
"""

import copy
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from helpers import Account, new_client, promote_to_admin
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pv_eval import report as rep
from pv_eval.__main__ import main
from pv_persistence.evaluation import get_run, latest_per_suite, list_runs, record_run

MakeAccount = Callable[..., Account]
ADMIN = "/api/v1/admin"


@pytest.fixture
def admin(app: FastAPI, make_account: MakeAccount, engine: Engine) -> Account:
    account = make_account(app)
    promote_to_admin(engine, account.email)
    return account


def passing_report() -> dict:  # type: ignore[type-arg]
    return rep.deterministic_report(now=datetime.now(UTC), sha="itest")


def failing_report() -> dict:  # type: ignore[type-arg]
    report = copy.deepcopy(passing_report())
    report["passed"] = False
    report["regressions"] = ["invented_leak_rate"]
    for m in report["metrics"]:
        if m["name"] == "invented_leak_rate":
            m["value"], m["status"], m["delta"] = 0.25, "below_limit", 0.25
    report["failures"].insert(
        0,
        {"suite": "extraction", "case_id": "job-99-99/invented/dropped", "expected": "every invented item dropped",
         "got": "2 invented item(s) kept", "note": "planted by a test"},
    )  # fmt: skip
    report["failure_count"] += 1
    report["suites"]["extraction"]["failed"] += 1
    return report


# ------------------------------------------------------------------------ who may ask


@pytest.mark.parametrize("path", [f"{ADMIN}/evaluation", f"{ADMIN}/evaluation/{uuid.uuid4()}"])
def test_only_an_admin_sees_evaluation(app: FastAPI, make_account: MakeAccount, path: str) -> None:
    assert new_client(app).get(path).status_code in (401, 404)
    assert make_account(app).client.get(path).status_code == 404


# ------------------------------------------------------------------------ storing and reading


def test_a_run_is_stored_and_read_back_whole(admin: Account, engine: Engine) -> None:
    report = passing_report()
    run_id = record_run(engine, report, trigger="ci")
    body = admin.client.get(f"{ADMIN}/evaluation/{run_id}").json()
    assert body["run"]["id"] == str(run_id) and body["run"]["suite"] == "deterministic"
    assert body["run"]["trigger"] == "ci" and body["run"]["git_sha"] == "itest"
    assert body["run"]["passed"] is True and body["run"]["dataset_version"] == "jobs-v1"
    assert body["run"]["case_count"] == report["case_count"] and body["run"]["regressions"] == []
    assert {"scoring", "eligibility_rules", "dataset"} <= set(body["versions"])
    names = {m["name"] for m in body["metrics"]}
    assert {"requirement_recall", "eligibility_weighted_error", "pairwise_agreement"} <= names
    recall = next(m for m in body["metrics"] if m["name"] == "requirement_recall")
    assert recall["value"] == 1.0 and recall["limit"] == 0.99 and recall["status"] == "ok"
    assert {s["name"] for s in body["suites"]} == {
        "extraction",
        "eligibility",
        "verdicts",
        "bands",
        "ranking",
        "claims",
    }
    assert body["failures"] and {"suite", "case_id", "expected", "got", "note"} <= set(
        body["failures"][0]
    )
    assert body["against"] is None


def test_the_list_shows_the_newest_first_and_the_latest_of_each_suite(
    admin: Account, engine: Engine
) -> None:
    first = record_run(engine, passing_report())
    second = record_run(engine, passing_report())
    body = admin.client.get(f"{ADMIN}/evaluation").json()
    ids = [r["id"] for r in body["runs"]]
    assert ids.index(str(second)) < ids.index(str(first))
    assert body["latest"]["deterministic"]["id"] == str(second)
    assert len(body["runs"]) <= 30


def test_a_regression_is_listed_by_name(admin: Account, engine: Engine) -> None:
    bad = record_run(engine, failing_report())
    try:
        run = next(
            r for r in admin.client.get(f"{ADMIN}/evaluation").json()["runs"] if r["id"] == str(bad)
        )
        assert run["passed"] is False and run["regressions"] == ["invented_leak_rate"]
        detail = admin.client.get(f"{ADMIN}/evaluation/{bad}").json()
        assert detail["failures"][0]["case_id"] == "job-99-99/invented/dropped"
        assert detail["failures"][0]["note"] == "planted by a test"
    finally:
        record_run(engine, passing_report())


def test_two_runs_can_be_compared_metric_by_metric(admin: Account, engine: Engine) -> None:
    good = record_run(engine, passing_report())
    bad = record_run(engine, failing_report())
    try:
        body = admin.client.get(f"{ADMIN}/evaluation/{bad}?against={good}").json()
        assert body["against"]["id"] == str(good)
        leak = next(m for m in body["metrics"] if m["name"] == "invented_leak_rate")
        assert leak["value"] == 0.25 and leak["previous"] == 0.0 and leak["change"] == 0.25
        steady = next(m for m in body["metrics"] if m["name"] == "requirement_recall")
        assert steady["change"] == 0.0
    finally:
        record_run(engine, passing_report())


def test_an_unknown_run_or_comparison_is_not_found(admin: Account, engine: Engine) -> None:
    run_id = record_run(engine, passing_report())
    assert admin.client.get(f"{ADMIN}/evaluation/{uuid.uuid4()}").status_code == 404
    assert (
        admin.client.get(f"{ADMIN}/evaluation/{run_id}?against={uuid.uuid4()}").status_code == 404
    )
    assert admin.client.get(f"{ADMIN}/evaluation/not-an-id").status_code == 422


# ------------------------------------------------------------------------ the record cannot be changed


def test_a_stored_result_cannot_be_changed_or_removed_by_the_application(engine: Engine) -> None:
    run_id = record_run(engine, passing_report())
    for statement in (
        "UPDATE evaluation_runs SET passed = false WHERE id = :i",
        "DELETE FROM evaluation_runs WHERE id = :i",
    ):
        with pytest.raises(DBAPIError), Session(engine) as db, db.begin():
            db.execute(text(statement), {"i": run_id})
    with Session(engine) as db:
        assert get_run(db, run_id) is not None


def test_the_table_is_a_system_table_with_no_row_level_security(engine: Engine) -> None:
    with engine.connect() as conn:
        enabled = conn.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = 'evaluation_runs'")
        ).scalar_one()
    assert enabled is False  # no row belongs to a person


def test_a_suite_or_trigger_outside_the_known_ones_is_refused(engine: Engine) -> None:
    for column, value in (("suite", "mystery"), ("trigger", "whenever")):
        report = passing_report()
        with pytest.raises(DBAPIError):
            if column == "suite":
                report["suite"] = value
                record_run(engine, report)
            else:
                record_run(engine, report, trigger=value)


# ------------------------------------------------------------------------ health and alerts


def test_health_shows_the_evaluation_as_passing_when_the_latest_run_passed(
    admin: Account, engine: Engine
) -> None:
    record_run(engine, passing_report())
    body = admin.client.get(f"{ADMIN}/health").json()
    part = next(c for c in body["components"] if c["name"] == "Evaluation")
    assert part["status"] == "ok" and "passed" in part["detail"]
    assert "evaluation_regressed" not in {a["key"] for a in body["alerts"]}


def test_a_failing_latest_run_raises_an_alert_and_a_later_pass_clears_it(
    admin: Account, engine: Engine
) -> None:
    record_run(engine, failing_report())
    try:
        body = admin.client.get(f"{ADMIN}/health").json()
        part = next(c for c in body["components"] if c["name"] == "Evaluation")
        assert part["status"] == "warning" and "deterministic" in part["detail"]
        alert = next(a for a in body["alerts"] if a["key"] == "evaluation_regressed")
        assert alert["severity"] == "warning" and "Open Evaluation" in alert["action"]
    finally:
        record_run(engine, passing_report())
    body = admin.client.get(f"{ADMIN}/health").json()
    assert "evaluation_regressed" not in {a["key"] for a in body["alerts"]}


# ------------------------------------------------------------------------ the command stores


def test_the_command_can_store_its_report(
    engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    with Session(engine) as db:
        before = len(list_runs(db, 1000))
    assert main(["run", "--store"]) == 0
    assert "Stored as run" in capsys.readouterr().out
    with Session(engine) as db:
        after = list_runs(db, 1000)
        assert len(after) == before + 1 and after[0].passed and after[0].suite == "deterministic"
        assert latest_per_suite(db)["deterministic"].id == after[0].id
