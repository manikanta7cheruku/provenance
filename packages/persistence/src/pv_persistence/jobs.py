"""Pasted job postings: create, read, extraction results, and the inputs for eligibility.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from pv_domain.eligibility import SeekerPreferences
from pv_domain.experience import years_of_experience
from pv_domain.job import JobErrorCode, JobParseStatus
from pv_domain.job_facts import GroundedJob
from pv_domain.states import RunState
from pv_domain.tasks import TASK_EXTRACT_JOB
from pv_persistence.analysis import delete_analysis
from pv_persistence.models import JobPosting, JobRequirement, ProfilePreferences
from pv_persistence.queue import enqueue
from pv_persistence.resumes import list_entries
from pv_persistence.runs import create_run, set_run_state

WORKFLOW_JOB_EXTRACTION = "job_extraction"


def get_posting(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> JobPosting | None:
    return db.execute(
        select(JobPosting).where(JobPosting.id == posting_id, JobPosting.owner_user_id == owner_id)
    ).scalar_one_or_none()


def find_by_hash(db: Session, owner_id: uuid.UUID, content_hash: str) -> JobPosting | None:
    return db.execute(
        select(JobPosting).where(
            JobPosting.owner_user_id == owner_id, JobPosting.content_hash == content_hash
        )
    ).scalar_one_or_none()


def list_postings(db: Session, owner_id: uuid.UUID, limit: int = 100) -> list[JobPosting]:
    return list(
        db.execute(
            select(JobPosting)
            .where(JobPosting.owner_user_id == owner_id)
            .order_by(JobPosting.created_at.desc(), JobPosting.id)
            .limit(limit)
        ).scalars()
    )


def list_requirements(
    db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID
) -> list[JobRequirement]:
    return list(
        db.execute(
            select(JobRequirement)
            .where(
                JobRequirement.owner_user_id == owner_id, JobRequirement.posting_id == posting_id
            )
            .order_by(JobRequirement.ordinal)
        ).scalars()
    )


def start_extraction(db: Session, posting: JobPosting, *, reanalyze: bool) -> uuid.UUID:
    """Create the workflow run and queue the extraction task, in the caller's transaction."""
    if reanalyze:
        posting.analysis_generation += 1
    run = create_run(
        db,
        owner_user_id=posting.owner_user_id,
        workflow_type=WORKFLOW_JOB_EXTRACTION,
        subject_type="job_posting",
        subject_id=str(posting.id),
    )
    posting.run_id = run.id
    posting.parse_status = JobParseStatus.QUEUED.value
    posting.error_code = None
    posting.updated_at = datetime.now(UTC)
    enqueue(
        db,
        task_type=TASK_EXTRACT_JOB,
        idempotency_key=f"{TASK_EXTRACT_JOB}:{posting.id}:{posting.analysis_generation}",
        payload={
            "args": {"posting_id": str(posting.id), "generation": posting.analysis_generation}
        },
        owner_user_id=posting.owner_user_id,
        run_id=run.id,
        max_attempts=3,
    )
    return run.id


def save_extraction(
    db: Session, posting: JobPosting, grounded: GroundedJob, *, prompt_version: str
) -> None:
    """Replace the stored analysis. Running it twice for the same posting leaves the same result."""
    # Verdicts point at the old requirements, so an evidence check of them is no longer valid.
    delete_analysis(db, posting.owner_user_id, posting.id)
    db.execute(delete(JobRequirement).where(JobRequirement.posting_id == posting.id))
    db.flush()
    for ordinal, item in enumerate(grounded.requirements):
        db.add(
            JobRequirement(
                posting_id=posting.id, owner_user_id=posting.owner_user_id, ordinal=ordinal, **item
            )
        )
    now = datetime.now(UTC)
    posting.title = grounded.title
    posting.company = grounded.company
    posting.facts = grounded.facts
    posting.facts_dropped = grounded.facts_dropped
    posting.requirements_dropped = grounded.requirements_dropped
    posting.parse_status = JobParseStatus.EXTRACTED.value
    posting.error_code = None
    posting.prompt_version = prompt_version
    posting.extracted_at = now
    posting.updated_at = now
    db.flush()


def mark_failed(db: Session, posting: JobPosting, code: JobErrorCode) -> None:
    posting.parse_status = JobParseStatus.FAILED.value
    posting.error_code = code.value
    posting.updated_at = datetime.now(UTC)


def cancel_waiting_tasks(db: Session, posting_id: uuid.UUID) -> None:
    """A posting that is deleted must not be read afterwards."""
    db.execute(
        text(
            "UPDATE tasks SET state = 'cancelled', finished_at = now(), updated_at = now() "
            "WHERE task_type = :t AND state IN ('queued', 'retry_scheduled') "
            "AND payload->'args'->>'posting_id' = :p"
        ),
        {"t": TASK_EXTRACT_JOB, "p": str(posting_id)},
    )


def fail_run(db: Session, run_id: uuid.UUID | None, code: JobErrorCode, *, can_retry: bool) -> None:
    if run_id is not None:
        set_run_state(
            db,
            run_id,
            RunState.FAILED,
            can_retry=can_retry,
            error_class="JOB_READ_FAILED",
            error_type="JobExtraction",
            error_message=code.value,
        )


def load_seeker(
    db: Session, owner_id: uuid.UUID, today: date | None = None
) -> tuple[SeekerPreferences, float | None]:
    """The person's answers and their years of experience, for the eligibility gates."""
    row = db.execute(
        select(ProfilePreferences).where(ProfilePreferences.owner_user_id == owner_id)
    ).scalar_one_or_none()
    prefs = SeekerPreferences()
    if row is not None:
        prefs = SeekerPreferences(
            authorized_countries=tuple(row.authorized_countries or ()),
            needs_sponsorship=row.needs_sponsorship,
            locations=tuple(row.locations or ()),
            open_to_relocate=row.open_to_relocate,
            remote_preference=row.remote_preference,
            employment_types=tuple(row.employment_types or ()),
            exclusions=tuple(row.exclusions or ()),
        )
    entries: list[tuple[str, dict[str, Any]]] = [
        (e.entry_type, e.data) for e in list_entries(db, owner_id)
    ]
    return prefs, years_of_experience(entries, today or datetime.now(UTC).date())
