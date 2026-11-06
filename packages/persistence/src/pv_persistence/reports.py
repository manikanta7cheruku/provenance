"""Report exports: the rows that track a report, and the loader that gathers what goes in it.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner. The loader reads stored data only, the same data the workbench shows, and applies
the same filters (pv_domain.pipeline.select), so a report holds exactly the jobs the person saw.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from pv_domain.pipeline import WorkQuery, clean_query, query_to_dict
from pv_domain.pipeline import select as select_rows
from pv_domain.report import (
    MAX_REPORT_JOBS,
    ReportEvidence,
    ReportInput,
    ReportJob,
    ReportRequirement,
    describe_query,
)
from pv_domain.tasks import TASK_BUILD_REPORT
from pv_persistence.models import (
    JobAnalysis,
    JobPosting,
    JobRequirement,
    ReportExport,
    RequirementVerdict,
)
from pv_persistence.queue import enqueue
from pv_persistence.runs import create_run
from pv_persistence.workrows import load_rows

WORKFLOW_REPORT_EXPORT = "report_export"
ACTIVE = ("queued", "building")

_SOURCE_WORDS = {"profile_entry": "Your profile", "user_answer": "Your answer to a question"}


def _entry_words(entry_type: object) -> str:
    return str(entry_type).replace("_", " ").capitalize() if entry_type else ""


# ---- the rows


def list_reports(db: Session, owner_id: uuid.UUID) -> list[ReportExport]:
    return list(
        db.execute(
            select(ReportExport)
            .where(ReportExport.owner_user_id == owner_id)
            .order_by(ReportExport.created_at.desc(), ReportExport.id)
        ).scalars()
    )


def get_report(db: Session, owner_id: uuid.UUID, report_id: uuid.UUID) -> ReportExport | None:
    return db.execute(
        select(ReportExport).where(
            ReportExport.id == report_id, ReportExport.owner_user_id == owner_id
        )
    ).scalar_one_or_none()


def count_active(db: Session, owner_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(ReportExport)
            .where(ReportExport.owner_user_id == owner_id, ReportExport.status.in_(ACTIVE))
        ).scalar_one()
    )


def start_report(
    db: Session,
    owner_id: uuid.UUID,
    fmt: str,
    query: WorkQuery,
    *,
    include_quotes: bool,
    retention_days: int,
    now: datetime | None = None,
) -> ReportExport:
    """Record a report and queue the work. The filters are stored cleaned, so the worker builds
    the report from exactly what was asked."""
    moment = now or datetime.now(UTC)
    report = ReportExport(
        owner_user_id=owner_id,
        format=fmt,
        params={"query": query_to_dict(query), "include_quotes": include_quotes},
        expires_at=moment + timedelta(days=retention_days),
    )
    db.add(report)
    db.flush()
    run = create_run(
        db,
        owner_user_id=owner_id,
        workflow_type=WORKFLOW_REPORT_EXPORT,
        subject_type="report_export",
        subject_id=str(report.id),
    )
    report.run_id = run.id
    enqueue(
        db,
        task_type=TASK_BUILD_REPORT,
        idempotency_key=f"{TASK_BUILD_REPORT}:{report.id}",
        payload={"args": {"report_id": str(report.id)}},
        owner_user_id=owner_id,
        run_id=run.id,
        max_attempts=3,
    )
    db.flush()
    return report


def finish_report(
    db: Session, report: ReportExport, *, storage_key: str, size_bytes: int, row_count: int
) -> None:
    report.status = "ready"
    report.storage_key = storage_key
    report.size_bytes = size_bytes
    report.row_count = row_count
    report.error_code = None
    report.finished_at = datetime.now(UTC)


def fail_report(db: Session, report: ReportExport, code: str) -> None:
    report.status = "failed"
    report.error_code = code
    report.finished_at = datetime.now(UTC)


def remove_report(db: Session, owner_id: uuid.UUID, report: ReportExport) -> str | None:
    """Delete one report row and cancel its waiting task. Returns the storage key to delete."""
    key = report.storage_key
    db.execute(
        text(
            "UPDATE tasks SET state = 'cancelled', finished_at = now(), updated_at = now() "
            "WHERE task_type = :t AND state IN ('queued', 'retry_scheduled') "
            "AND owner_user_id = :o AND payload->'args'->>'report_id' = :r"
        ),
        {"t": TASK_BUILD_REPORT, "o": owner_id, "r": str(report.id)},
    )
    db.delete(report)
    db.flush()
    return key


def expire_reports(
    db: Session, owner_id: uuid.UUID, keep: int, now: datetime | None = None
) -> list[str]:
    """Remove reports past their expiry and any beyond the newest `keep` that are not in progress.
    Returns the storage keys of the files to delete."""
    moment = now or datetime.now(UTC)
    keys: list[str] = []
    for position, report in enumerate(list_reports(db, owner_id)):
        if report.status in ACTIVE:
            continue
        if report.expires_at <= moment or position >= keep:
            key = remove_report(db, owner_id, report)
            if key:
                keys.append(key)
    return keys


# ---- gathering what goes in a report


def _verdict_maps(
    db: Session, owner_id: uuid.UUID, posting_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, list[JobRequirement]], dict[uuid.UUID, RequirementVerdict]]:
    requirements: dict[uuid.UUID, list[JobRequirement]] = {p: [] for p in posting_ids}
    if not posting_ids:
        return requirements, {}
    for req in db.execute(
        select(JobRequirement)
        .where(JobRequirement.owner_user_id == owner_id, JobRequirement.posting_id.in_(posting_ids))
        .order_by(JobRequirement.posting_id, JobRequirement.ordinal)
    ).scalars():
        requirements[req.posting_id].append(req)
    analyses = [
        a.id
        for a in db.execute(
            select(JobAnalysis).where(
                JobAnalysis.owner_user_id == owner_id,
                JobAnalysis.posting_id.in_(posting_ids),
                JobAnalysis.status == "complete",
            )
        ).scalars()
    ]
    verdicts: dict[uuid.UUID, RequirementVerdict] = {}
    if analyses:
        for v in db.execute(
            select(RequirementVerdict).where(
                RequirementVerdict.owner_user_id == owner_id,
                RequirementVerdict.analysis_id.in_(analyses),
            )
        ).scalars():
            verdicts[v.requirement_id] = v
    return requirements, verdicts


def _requirement(
    req: JobRequirement, verdict: RequirementVerdict | None, include_quotes: bool
) -> ReportRequirement:
    evidence: list[ReportEvidence] = []
    if verdict is not None:
        seen: set[tuple[str, str, str]] = set()
        for c in verdict.citations:
            source = str(c.get("source_type", ""))
            words = _SOURCE_WORDS.get(
                source, "GitHub" if source.startswith("github") else "Your profile"
            )
            entry = _entry_words(c.get("entry_type"))
            quote = str(c.get("quote", "")) if include_quotes else ""
            if (words, entry, quote) not in seen:
                seen.add((words, entry, quote))
                evidence.append(ReportEvidence(words, entry, quote))
    return ReportRequirement(
        text=req.text,
        importance={"required": "Required", "preferred": "Preferred"}.get(req.kind, ""),
        verdict=verdict.verdict if verdict is not None else "",
        reason=verdict.reason if verdict is not None else "",
        evidence=tuple(evidence),
    )


def load_report_input(
    db: Session,
    owner_id: uuid.UUID,
    params: dict[str, Any],
    *,
    now: datetime | None = None,
) -> ReportInput:
    """The jobs the person's saved filters choose, with their requirements and evidence."""
    raw = params.get("query")
    query = clean_query(raw if isinstance(raw, dict) else {})
    include_quotes = bool(params.get("include_quotes"))
    postings, rows, reasons = load_rows(db, owner_id, MAX_REPORT_JOBS + 1)
    truncated = len(postings) > MAX_REPORT_JOBS
    rows = rows[:MAX_REPORT_JOBS]
    chosen = select_rows(rows, query)
    by_id: dict[str, JobPosting] = {str(p.id): p for p in postings}
    requirements, verdicts = _verdict_maps(db, owner_id, [uuid.UUID(r.id) for r in chosen])
    jobs: list[ReportJob] = []
    for row in chosen:
        posting = by_id[row.id]
        jobs.append(
            ReportJob(
                id=row.id,
                title=row.title,
                company=row.company,
                location=row.location,
                work_mode=row.work_mode or "",
                employment_type=row.employment_type or "",
                seniority=row.seniority or "",
                source=row.source_name,
                acquisition=row.acquisition_method,
                link=posting.source_url or "",
                eligibility=row.eligibility or "",
                band=row.band or "",
                recommendation=reasons.get(posting.id, ""),
                state=row.state,
                applied_on=row.applied_at.date().isoformat() if row.applied_at else "",
                note=row.note,
                added_on=row.created_at.date().isoformat(),
                requirements=tuple(
                    _requirement(req, verdicts.get(req.id), include_quotes)
                    for req in requirements.get(posting.id, [])
                ),
            )
        )
    return ReportInput(
        generated_at=now or datetime.now(UTC),
        criteria=describe_query(query),
        jobs=tuple(jobs),
        include_quotes=include_quotes,
        truncated=truncated,
    )
