"""The resume studio: documents, saved versions and PDF exports.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner.

Saving uses the revision number as a lock: a save says which revision it was made from, and if the
stored revision has moved on (another tab, another device) the save is refused with the current
revision so the person can choose, instead of one tab silently overwriting the other.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from pv_domain.resume_doc import MAX_VERSIONS
from pv_domain.tasks import TASK_RENDER_RESUME
from pv_persistence.models import ResumeDocument, ResumeDocumentVersion, ResumeExport
from pv_persistence.queue import enqueue
from pv_persistence.runs import create_run

WORKFLOW_RESUME_EXPORT = "resume_export"
# Autosave can fire every few seconds. A restore point is kept at most this often.
VERSION_INTERVAL = timedelta(minutes=2)


@dataclass(frozen=True)
class RevisionConflict(Exception):
    current_revision: int


def list_documents(db: Session, owner_id: uuid.UUID) -> list[ResumeDocument]:
    return list(
        db.execute(
            select(ResumeDocument)
            .where(ResumeDocument.owner_user_id == owner_id)
            .order_by(ResumeDocument.created_at)
        ).scalars()
    )


def get_document(db: Session, owner_id: uuid.UUID, document_id: uuid.UUID) -> ResumeDocument | None:
    return db.execute(
        select(ResumeDocument).where(
            ResumeDocument.id == document_id, ResumeDocument.owner_user_id == owner_id
        )
    ).scalar_one_or_none()


def create_document(
    db: Session, owner_id: uuid.UUID, title: str, content: dict[str, Any]
) -> ResumeDocument:
    document = ResumeDocument(owner_user_id=owner_id, title=title, content=content)
    db.add(document)
    db.flush()
    return document


def _prune_versions(db: Session, document_id: uuid.UUID) -> None:
    keep = (
        select(ResumeDocumentVersion.id)
        .where(ResumeDocumentVersion.document_id == document_id)
        .order_by(ResumeDocumentVersion.revision.desc())
        .limit(MAX_VERSIONS)
    )
    db.execute(
        delete(ResumeDocumentVersion).where(
            ResumeDocumentVersion.document_id == document_id,
            ResumeDocumentVersion.id.not_in(keep),
        )
    )


def _remember(db: Session, document: ResumeDocument, *, force: bool) -> None:
    """Keep the content being replaced as a restore point, if the last one is old enough."""
    last = db.execute(
        select(func.max(ResumeDocumentVersion.created_at)).where(
            ResumeDocumentVersion.document_id == document.id
        )
    ).scalar_one()
    if not force and last is not None and datetime.now(UTC) - last < VERSION_INTERVAL:
        return
    exists = db.execute(
        select(ResumeDocumentVersion.id).where(
            ResumeDocumentVersion.document_id == document.id,
            ResumeDocumentVersion.revision == document.revision,
        )
    ).first()
    if exists is None:
        db.add(
            ResumeDocumentVersion(
                owner_user_id=document.owner_user_id,
                document_id=document.id,
                revision=document.revision,
                content=document.content,
            )
        )
        db.flush()
        _prune_versions(db, document.id)


def save_document(
    db: Session,
    document: ResumeDocument,
    content: dict[str, Any],
    *,
    expected_revision: int,
    title: str | None = None,
    checkpoint: bool = False,
) -> ResumeDocument:
    """Replace the content if the stored revision is still the one the caller started from."""
    if document.revision != expected_revision:
        raise RevisionConflict(document.revision)
    _remember(db, document, force=checkpoint)
    updated = db.execute(
        text(
            "UPDATE resume_documents SET content = CAST(:c AS jsonb), revision = revision + 1, "
            "title = COALESCE(:t, title), updated_at = now() "
            "WHERE id = :id AND owner_user_id = :o AND revision = :r RETURNING revision"
        ),
        {
            "c": json.dumps(content),
            "t": title,
            "id": document.id,
            "o": document.owner_user_id,
            "r": expected_revision,
        },
    ).first()
    if updated is None:
        current: int = db.execute(
            text("SELECT revision FROM resume_documents WHERE id = :id"), {"id": document.id}
        ).scalar_one()
        raise RevisionConflict(int(current))
    db.refresh(document)
    return document


def list_versions(
    db: Session, owner_id: uuid.UUID, document_id: uuid.UUID
) -> list[ResumeDocumentVersion]:
    return list(
        db.execute(
            select(ResumeDocumentVersion)
            .where(
                ResumeDocumentVersion.owner_user_id == owner_id,
                ResumeDocumentVersion.document_id == document_id,
            )
            .order_by(ResumeDocumentVersion.revision.desc())
        ).scalars()
    )


def get_version(
    db: Session, owner_id: uuid.UUID, document_id: uuid.UUID, version_id: uuid.UUID
) -> ResumeDocumentVersion | None:
    return db.execute(
        select(ResumeDocumentVersion).where(
            ResumeDocumentVersion.id == version_id,
            ResumeDocumentVersion.document_id == document_id,
            ResumeDocumentVersion.owner_user_id == owner_id,
        )
    ).scalar_one_or_none()


def delete_document(db: Session, owner_id: uuid.UUID, document: ResumeDocument) -> list[str]:
    """Remove a resume. Returns the storage keys of its PDFs so the caller can delete the files."""
    keys = [
        row.storage_key
        for row in db.execute(
            select(ResumeExport.storage_key).where(
                ResumeExport.document_id == document.id,
                ResumeExport.owner_user_id == owner_id,
                ResumeExport.storage_key.is_not(None),
            )
        )
    ]
    db.execute(
        text(
            "UPDATE tasks SET state = 'cancelled', finished_at = now(), updated_at = now() "
            "WHERE task_type = :t AND state IN ('queued', 'retry_scheduled') "
            "AND payload->'args'->>'document_id' = :d"
        ),
        {"t": TASK_RENDER_RESUME, "d": str(document.id)},
    )
    db.delete(document)
    db.flush()
    return keys


# ---- exports


def list_exports(db: Session, owner_id: uuid.UUID, document_id: uuid.UUID) -> list[ResumeExport]:
    return list(
        db.execute(
            select(ResumeExport)
            .where(ResumeExport.owner_user_id == owner_id, ResumeExport.document_id == document_id)
            .order_by(ResumeExport.created_at.desc())
        ).scalars()
    )


def get_export(db: Session, owner_id: uuid.UUID, export_id: uuid.UUID) -> ResumeExport | None:
    return db.execute(
        select(ResumeExport).where(
            ResumeExport.id == export_id, ResumeExport.owner_user_id == owner_id
        )
    ).scalar_one_or_none()


def start_export(db: Session, document: ResumeDocument) -> ResumeExport:
    """Record an export of the current revision and queue the render."""
    export = ResumeExport(
        owner_user_id=document.owner_user_id, document_id=document.id, revision=document.revision
    )
    db.add(export)
    db.flush()
    run = create_run(
        db,
        owner_user_id=document.owner_user_id,
        workflow_type=WORKFLOW_RESUME_EXPORT,
        subject_type="resume_document",
        subject_id=str(document.id),
    )
    export.run_id = run.id
    enqueue(
        db,
        task_type=TASK_RENDER_RESUME,
        idempotency_key=f"{TASK_RENDER_RESUME}:{export.id}",
        payload={"args": {"export_id": str(export.id), "document_id": str(document.id)}},
        owner_user_id=document.owner_user_id,
        run_id=run.id,
        max_attempts=3,
    )
    db.flush()
    return export


def prune_exports(db: Session, owner_id: uuid.UUID, document_id: uuid.UUID, keep: int) -> list[str]:
    """Keep the newest `keep` exports. Returns the storage keys of the ones removed."""
    rows = list_exports(db, owner_id, document_id)
    removed: list[str] = []
    for export in rows[keep:]:
        if export.status in ("queued", "rendering"):
            continue
        if export.storage_key:
            removed.append(export.storage_key)
        db.delete(export)
    db.flush()
    return removed


def finish_export(
    db: Session,
    export: ResumeExport,
    *,
    storage_key: str,
    size_bytes: int,
    page_count: int,
) -> None:
    export.status = "ready"
    export.storage_key = storage_key
    export.size_bytes = size_bytes
    export.page_count = page_count
    export.error_code = None
    export.finished_at = datetime.now(UTC)


def fail_export(db: Session, export: ResumeExport, code: str) -> None:
    export.status = "failed"
    export.error_code = code
    export.finished_at = datetime.now(UTC)
