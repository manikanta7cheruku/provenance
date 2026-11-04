"""Import batches and their reports, and storing an imported posting.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner. The report never holds posting text: a row is a number, a status, a short code,
a sentence and (when it worked) the id of the posting.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pv_domain.job_import import BatchStatus, ItemStatus, PostingDraft
from pv_domain.tasks import TASK_IMPORT_FILE, TASK_IMPORT_URL
from pv_persistence.jobs import find_by_hash, start_extraction
from pv_persistence.models import ImportBatch, ImportItem, JobPosting
from pv_persistence.queue import enqueue

MAX_BATCHES_LISTED = 20


def create_file_batch(
    db: Session, *, owner_id: uuid.UUID, kind: str, label: str, default_source: str, file_key: str
) -> ImportBatch:
    """A spreadsheet upload, with its task, in the caller's transaction."""
    batch = ImportBatch(
        owner_user_id=owner_id,
        kind=kind,
        label=label,
        default_source=default_source,
        file_key=file_key,
    )
    db.add(batch)
    db.flush()
    enqueue(
        db,
        task_type=TASK_IMPORT_FILE,
        idempotency_key=f"{TASK_IMPORT_FILE}:{batch.id}",
        payload={"args": {"batch_id": str(batch.id)}},
        owner_user_id=owner_id,
        max_attempts=3,
    )
    return batch


def create_url_batch(
    db: Session, *, owner_id: uuid.UUID, url: str, host: str, default_source: str
) -> ImportBatch:
    """One web address to read, with its single report row and its task."""
    batch = ImportBatch(
        owner_user_id=owner_id,
        kind="url",
        label=host,
        default_source=default_source,
        total_rows=1,
    )
    db.add(batch)
    db.flush()
    db.add(ImportItem(batch_id=batch.id, owner_user_id=owner_id, row_number=1, source_url=url))
    enqueue(
        db,
        task_type=TASK_IMPORT_URL,
        idempotency_key=f"{TASK_IMPORT_URL}:{batch.id}",
        payload={"args": {"batch_id": str(batch.id)}},
        owner_user_id=owner_id,
        max_attempts=3,
    )
    return batch


def get_batch(db: Session, owner_id: uuid.UUID, batch_id: uuid.UUID) -> ImportBatch | None:
    return db.execute(
        select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.owner_user_id == owner_id)
    ).scalar_one_or_none()


def list_batches(db: Session, owner_id: uuid.UUID) -> list[ImportBatch]:
    return list(
        db.execute(
            select(ImportBatch)
            .where(ImportBatch.owner_user_id == owner_id)
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id)
            .limit(MAX_BATCHES_LISTED)
        ).scalars()
    )


def list_items(db: Session, owner_id: uuid.UUID, batch_id: uuid.UUID) -> list[ImportItem]:
    return list(
        db.execute(
            select(ImportItem)
            .where(ImportItem.batch_id == batch_id, ImportItem.owner_user_id == owner_id)
            .order_by(ImportItem.row_number)
        ).scalars()
    )


def store_draft(
    db: Session, *, owner_id: uuid.UUID, draft: PostingDraft, acquisition: str
) -> tuple[JobPosting, bool]:
    """Save a draft as a private posting and queue its reading. Returns the posting and whether it
    was new. The same text already saved is returned as it is (second item False)."""
    existing = find_by_hash(db, owner_id, draft.content_hash)
    if existing is not None:
        return existing, False
    posting = JobPosting(
        owner_user_id=owner_id,
        source_name=draft.source_name,
        acquisition_method=acquisition,
        source_url=draft.link,
        raw_text=draft.text,
        content_hash=draft.content_hash,
        title=draft.title,
        company=draft.company,
    )
    try:
        with db.begin_nested():
            db.add(posting)
            db.flush()
    except IntegrityError:
        # The same posting was saved a moment ago by another request: show that one.
        found = find_by_hash(db, owner_id, draft.content_hash)
        if found is None:
            raise
        return found, False
    start_extraction(db, posting, reanalyze=False)
    db.flush()
    return posting, True


def finish_batch(
    db: Session, batch: ImportBatch, *, status: BatchStatus, error_code: str | None = None
) -> None:
    """Count the report rows into the batch and close it."""
    items = list_items(db, batch.owner_user_id, batch.id)
    batch.created_count = sum(1 for i in items if i.status == ItemStatus.CREATED)
    batch.duplicate_count = sum(1 for i in items if i.status == ItemStatus.DUPLICATE)
    batch.rejected_count = sum(1 for i in items if i.status == ItemStatus.REJECTED)
    batch.total_rows = max(batch.total_rows, len(items))
    batch.status = status.value
    batch.error_code = error_code
    batch.file_key = None  # the uploaded file is deleted by the caller; the key is not kept
    batch.finished_at = datetime.now(UTC)
