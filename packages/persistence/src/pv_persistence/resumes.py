"""Resume and profile-entry operations shared by the API and the worker.

Call everything here inside tenant_session (Row Level Security applies). The functions still
filter by owner, so a missing policy could not leak rows (two independent layers).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pv_domain.profile import entry_key, flagged_fields
from pv_domain.resume import ParseStatus, ReviewStatus
from pv_domain.tasks import TASK_PARSE_RESUME
from pv_persistence.models import ProfileEntry, Resume
from pv_persistence.queue import enqueue
from pv_persistence.runs import create_run

WORKFLOW_RESUME_PARSE = "resume_parse"


def get_resume(db: Session, owner_id: uuid.UUID) -> Resume | None:
    return db.execute(select(Resume).where(Resume.owner_user_id == owner_id)).scalar_one_or_none()


def list_entries(db: Session, owner_id: uuid.UUID) -> list[ProfileEntry]:
    return list(
        db.execute(
            select(ProfileEntry)
            .where(ProfileEntry.owner_user_id == owner_id)
            .order_by(ProfileEntry.position, ProfileEntry.created_at)
        ).scalars()
    )


def flagged_entry_count(entries: list[ProfileEntry]) -> int:
    return sum(1 for entry in entries if flagged_fields(entry.entry_type, entry.data))


def start_parse(db: Session, resume: Resume, *, reparse: bool) -> uuid.UUID:
    """Create the workflow run and queue the parse task, in the caller's transaction.

    The task is queued together with the state change, so a crash can never leave a resume
    marked "uploaded" with no task behind it, or a task with no resume.
    """
    if reparse:
        resume.parse_generation += 1
    run = create_run(
        db,
        owner_user_id=resume.owner_user_id,
        workflow_type=WORKFLOW_RESUME_PARSE,
        subject_type="resume",
        subject_id=str(resume.id),
    )
    resume.run_id = run.id
    resume.parse_status = ParseStatus.UPLOADED.value
    resume.review_status = ReviewStatus.PENDING.value
    resume.confirmed_at = None
    resume.error_code = None
    resume.updated_at = datetime.now(UTC)
    enqueue(
        db,
        task_type=TASK_PARSE_RESUME,
        idempotency_key=f"{TASK_PARSE_RESUME}:{resume.id}:{resume.parse_generation}",
        payload={"args": {"resume_id": str(resume.id), "generation": resume.parse_generation}},
        owner_user_id=resume.owner_user_id,
        run_id=run.id,
        max_attempts=3,
    )
    return run.id


def replace_parsed_entries(
    db: Session,
    *,
    owner_id: uuid.UUID,
    resume_id: uuid.UUID,
    entries: list[tuple[str, dict[str, Any]]],
) -> int:
    """Swap in freshly parsed entries without touching anything the person has edited.

    Entries created by an earlier parse and never edited are replaced. Entries the person
    edited or added stay exactly as they are, and a parsed entry that matches one of them is
    skipped, so a re-parse never duplicates or overwrites the person's work.
    Returns how many parsed entries were stored.
    """
    existing = list_entries(db, owner_id)
    kept: list[ProfileEntry] = []
    for entry in existing:
        if entry.source == "resume" and not entry.user_edited:
            db.delete(entry)
        else:
            kept.append(entry)
    seen = {entry_key(entry.entry_type, entry.data) for entry in kept}
    seen |= {entry.source_key for entry in kept if entry.source_key}
    position = max((entry.position for entry in kept), default=-1) + 1
    stored = 0
    for entry_type, clean in entries:
        key = entry_key(entry_type, clean)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            ProfileEntry(
                owner_user_id=owner_id,
                entry_type=entry_type,
                data=clean,
                user_edited=False,
                source="resume",
                source_resume_id=resume_id,
                source_key=key,
                position=position,
            )
        )
        position += 1
        stored += 1
    db.flush()
    return stored
