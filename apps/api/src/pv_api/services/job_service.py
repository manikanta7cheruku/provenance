"""Pasted job postings: paste, list, read, re-read, delete, and the eligibility shown with them.

Everything runs in one tenant session (Row Level Security) and filters by the signed-in owner. A
posting that belongs to someone else is "not found", never "forbidden". Eligibility is computed
when a posting is read, from the person's current answers and entries, so a new answer applies at
once and nothing stale is stored.
"""

import uuid
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    EligibilityOut,
    FactOut,
    GateOut,
    JobCreate,
    JobCreatedOut,
    JobDetailOut,
    JobSummaryOut,
    RequirementOut,
)
from pv_domain.eligibility import EligibilityResult, evaluate_eligibility
from pv_domain.failures import FailureClass
from pv_domain.job import (
    ACQUISITION_USER_PASTE,
    JOB_ERROR_MESSAGES,
    MAX_POSTING_CHARS,
    MIN_POSTING_CHARS,
    JobParseStatus,
    clean_posting_text,
    job_ui_state,
    posting_content_hash,
)
from pv_domain.job_facts import posting_facts_from_record
from pv_persistence.analysis import delete_analysis
from pv_persistence.audit import record_audit
from pv_persistence.jobs import (
    cancel_waiting_tasks,
    find_by_hash,
    get_posting,
    list_postings,
    list_requirements,
    load_seeker,
    start_extraction,
)
from pv_persistence.models import JobPosting, JobRequirement
from pv_persistence.tenancy import tenant_session


def not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


def _fact_value(posting: JobPosting, key: str) -> str | None:
    item = posting.facts.get(key)
    if not isinstance(item, dict):
        return None
    value = item.get("value")
    return (
        ", ".join(value) if isinstance(value, list) else str(value) if value is not None else None
    )


def _eligibility(db: Session, posting: JobPosting) -> EligibilityResult | None:
    if posting.parse_status != JobParseStatus.EXTRACTED:
        return None
    prefs, years = load_seeker(db, posting.owner_user_id)
    facts = posting_facts_from_record(
        posting.raw_text, posting.title, posting.company, posting.facts
    )
    return evaluate_eligibility(facts, prefs, years)


def _eligibility_out(result: EligibilityResult) -> EligibilityOut:
    return EligibilityOut(
        state=result.state.value,
        rules_version=result.rules_version,
        gates=[
            GateOut(
                gate=g.gate,
                label=g.label,
                state=g.state.value,
                reason=g.reason,
                posting_quote=g.posting_quote,
            )
            for g in result.gates
        ],
    )


def _summary_fields(
    posting: JobPosting, result: EligibilityResult | None, count: int
) -> dict[str, Any]:
    failed = posting.parse_status == JobParseStatus.FAILED
    return {
        "id": posting.id,
        "title": posting.title,
        "company": posting.company,
        "source_name": posting.source_name,
        "acquisition_method": posting.acquisition_method,
        "ui_state": job_ui_state(posting.parse_status).value,
        "can_retry": posting.parse_status in (JobParseStatus.EXTRACTED, JobParseStatus.FAILED),
        "error_message": JOB_ERROR_MESSAGES.get(posting.error_code or "") if failed else None,
        "eligibility": result.state.value if result else None,
        "work_mode": _fact_value(posting, "work_mode"),
        "location": _fact_value(posting, "location"),
        "requirement_count": count,
        "created_at": posting.created_at,
    }


def _detail(db: Session, posting: JobPosting) -> JobDetailOut:
    requirements = list_requirements(db, posting.owner_user_id, posting.id)
    result = _eligibility(db, posting)
    fields = _summary_fields(posting, result, len(requirements))
    return JobDetailOut(
        **fields,
        source_url=posting.source_url,
        visibility=posting.visibility,
        facts={
            key: FactOut(value=item["value"], quote=item["quote"])
            for key, item in posting.facts.items()
            if isinstance(item, dict) and "value" in item
        },
        requirements=[_requirement(r) for r in requirements],
        eligibility_detail=_eligibility_out(result) if result else None,
        facts_dropped=posting.facts_dropped,
        requirements_dropped=posting.requirements_dropped,
        prompt_version=posting.prompt_version,
        run_id=posting.run_id,
        extracted_at=posting.extracted_at,
        text=posting.raw_text,
    )


def _requirement(r: JobRequirement) -> RequirementOut:
    return RequirementOut(
        id=r.id, ordinal=r.ordinal, text=r.text, kind=r.kind,  # type: ignore[arg-type]
        category=r.category, years_min=r.years_min, quote=r.quote,
        quote_start=r.quote_start, quote_end=r.quote_end,
    )  # fmt: skip


def paste(
    engine: Engine, *, user_id: uuid.UUID, payload: JobCreate, ip_hash: str | None
) -> JobCreatedOut:
    text = clean_posting_text(payload.text)
    problem = None
    if len(text) < MIN_POSTING_CHARS:
        problem = "This looks too short to be a job posting. Paste the whole description."
    elif len(text) > MAX_POSTING_CHARS:
        problem = f"This is over {MAX_POSTING_CHARS:,} characters. Paste the description only."
    if problem:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"text": problem},
        )
    digest = posting_content_hash(text)
    created = False
    try:
        with tenant_session(engine, user_id) as db:
            posting = find_by_hash(db, user_id, digest)
            if posting is None:
                posting = JobPosting(
                    owner_user_id=user_id,
                    source_name=payload.source_name,
                    acquisition_method=ACQUISITION_USER_PASTE,
                    source_url=payload.source_url,
                    raw_text=text,
                    content_hash=digest,
                )
                db.add(posting)
                db.flush()
                start_extraction(db, posting, reanalyze=False)
                db.flush()
                created = True
            out = _detail(db, posting)
    except IntegrityError:
        # Two identical pastes at once: the other one won. Show it.
        with tenant_session(engine, user_id) as db:
            existing = find_by_hash(db, user_id, digest)
            if existing is None:
                raise
            out = _detail(db, existing)
    if created:
        record_audit(
            engine, category="audit", action="job.pasted", actor_user_id=user_id,
            target_type="job_posting", target_id=str(out.id), ip_hash=ip_hash,
            metadata={"source": payload.source_name, "characters": len(text)},
        )  # fmt: skip
    return JobCreatedOut(job=out, duplicate=not created)


def list_jobs(engine: Engine, user_id: uuid.UUID) -> list[JobSummaryOut]:
    with tenant_session(engine, user_id) as db:
        out: list[JobSummaryOut] = []
        for posting in list_postings(db, user_id):
            count = len(list_requirements(db, user_id, posting.id))
            out.append(JobSummaryOut(**_summary_fields(posting, _eligibility(db, posting), count)))
        return out


def get_job(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID) -> JobDetailOut:
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        return _detail(db, posting)


def reanalyze(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID) -> JobDetailOut:
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        if posting.parse_status not in (JobParseStatus.EXTRACTED, JobParseStatus.FAILED):
            raise ApiError(
                409, "PARSE_IN_PROGRESS", "This posting is still being read. Please wait.",
                failure_class=FailureClass.USER_ACTION_REQUIRED,
            )  # fmt: skip
        start_extraction(db, posting, reanalyze=True)
        db.flush()
        return _detail(db, posting)


def delete_job(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, ip_hash: str | None) -> None:
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        cancel_waiting_tasks(db, posting.id)
        delete_analysis(db, user_id, posting.id)
        db.delete(posting)
    record_audit(
        engine, category="audit", action="job.deleted", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
    )  # fmt: skip
