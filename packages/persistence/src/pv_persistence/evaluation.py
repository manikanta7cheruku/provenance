"""Stored evaluation runs: add one, list them, read one.

A system table with synthetic data only, so these functions take a plain session or engine (no
tenant). The application role can add and read rows and cannot change or remove them.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_persistence.models import EvaluationRun


def record_run(engine: Engine, report: dict[str, Any], *, trigger: str = "manual") -> uuid.UUID:
    """Store a report made by pv_eval.report.build_report."""
    row = EvaluationRun(
        suite=report["suite"],
        trigger=trigger,
        dataset_version=report["dataset_version"],
        git_sha=report.get("git_sha"),
        model=report.get("model"),
        passed=bool(report["passed"]),
        case_count=int(report["case_count"]),
        failure_count=int(report["failure_count"]),
        versions=dict(report.get("versions", {})),
        metrics=list(report.get("metrics", [])),
        suites=dict(report.get("suites", {})),
        failures=list(report.get("failures", [])),
    )
    with Session(engine) as db, db.begin():
        db.add(row)
        db.flush()
        return row.id


def list_runs(db: Session, limit: int = 30) -> list[EvaluationRun]:
    return list(
        db.execute(
            select(EvaluationRun)
            .order_by(EvaluationRun.created_at.desc(), EvaluationRun.id)
            .limit(limit)
        ).scalars()
    )


def get_run(db: Session, run_id: uuid.UUID) -> EvaluationRun | None:
    return db.get(EvaluationRun, run_id)


def latest_per_suite(db: Session) -> dict[str, EvaluationRun]:
    out: dict[str, EvaluationRun] = {}
    for run in db.execute(
        select(EvaluationRun).order_by(EvaluationRun.created_at.desc(), EvaluationRun.id)
    ).scalars():
        out.setdefault(run.suite, run)
    return out
