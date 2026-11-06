"""The evaluation views: the stored runs, one run in full, and a comparison between two runs.

Reads the evaluation_runs system table only. The dataset is synthetic, so a run holds no personal
data, and an administrator may read all of it. A comparison puts the metrics of one run next to
another's, matched by name, so a regression is a number that moved, not a feeling.
"""

import uuid
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    EvalDetailOut,
    EvalFailureOut,
    EvalListOut,
    EvalMetricOut,
    EvalRunOut,
    EvalSuiteOut,
)
from pv_domain.failures import FailureClass
from pv_persistence.evaluation import get_run, latest_per_suite, list_runs
from pv_persistence.models import EvaluationRun


def _out(run: EvaluationRun) -> EvalRunOut:
    return EvalRunOut(
        id=run.id,
        created_at=run.created_at,
        suite=run.suite,  # type: ignore[arg-type]
        trigger=run.trigger,
        dataset_version=run.dataset_version,
        git_sha=run.git_sha,
        model=run.model,
        passed=run.passed,
        case_count=run.case_count,
        failure_count=run.failure_count,
        regressions=[
            str(m["name"]) for m in run.metrics if m.get("status") in ("regressed", "below_limit")
        ],
    )


def _not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


def listing(engine: Engine, limit: int = 30) -> EvalListOut:
    with Session(engine) as db:
        return EvalListOut(
            runs=[_out(r) for r in list_runs(db, limit)],
            latest={suite: _out(r) for suite, r in latest_per_suite(db).items()},
        )


def detail(engine: Engine, run_id: uuid.UUID, against: uuid.UUID | None) -> EvalDetailOut:
    with Session(engine) as db:
        run = get_run(db, run_id)
        if run is None:
            raise _not_found()
        other = get_run(db, against) if against is not None else None
        if against is not None and other is None:
            raise _not_found()
        previous: dict[str, float] = (
            {str(m["name"]): float(m["value"]) for m in other.metrics} if other else {}
        )
        metrics: list[EvalMetricOut] = []
        for m in run.metrics:
            item: dict[str, Any] = dict(m)
            before = previous.get(str(item["name"]))
            item["previous"] = before
            item["change"] = None if before is None else round(float(item["value"]) - before, 4)
            metrics.append(EvalMetricOut(**item))
        return EvalDetailOut(
            run=_out(run),
            versions={str(k): str(v) for k, v in run.versions.items()},
            metrics=metrics,
            suites=[
                EvalSuiteOut(
                    name=name, cases=int(v.get("cases", 0)), failed=int(v.get("failed", 0))
                )
                for name, v in run.suites.items()
            ],
            failures=[
                EvalFailureOut(
                    suite=str(f.get("suite", "")),
                    case_id=str(f.get("case_id", "")),
                    expected=str(f.get("expected", "")),
                    got=str(f.get("got", "")),
                    note=str(f.get("note", "")),
                )
                for f in run.failures
            ],
            against=_out(other) if other else None,
        )
