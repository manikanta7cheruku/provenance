"""Stored pictures for the resume studio.

Call everything here inside tenant_session (Row Level Security applies). Every statement also filters
by owner. What a picture is allowed to be is decided in pv_domain.resume_images and pv_files.images.
This module stores the row and answers: which pictures does this person own, how many and how big,
and is one still used by a resume.
"""

import uuid

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pv_domain.resume_images import ImageInfo
from pv_persistence.models import ResumeImage


def get_image(db: Session, owner_id: uuid.UUID, image_id: uuid.UUID) -> ResumeImage | None:
    return db.execute(
        select(ResumeImage).where(ResumeImage.owner_user_id == owner_id, ResumeImage.id == image_id)
    ).scalar_one_or_none()


def list_images(db: Session, owner_id: uuid.UUID) -> list[ResumeImage]:
    return list(
        db.execute(
            select(ResumeImage)
            .where(ResumeImage.owner_user_id == owner_id)
            .order_by(ResumeImage.created_at.desc(), ResumeImage.id)
        ).scalars()
    )


def find_by_hash(db: Session, owner_id: uuid.UUID, digest: str) -> ResumeImage | None:
    return db.execute(
        select(ResumeImage).where(
            ResumeImage.owner_user_id == owner_id, ResumeImage.sha256 == digest
        )
    ).scalar_one_or_none()


def totals(db: Session, owner_id: uuid.UUID) -> tuple[int, int]:
    """How many pictures the person has and how many bytes they take."""
    count, size = db.execute(
        select(func.count(), func.coalesce(func.sum(ResumeImage.size_bytes), 0)).where(
            ResumeImage.owner_user_id == owner_id
        )
    ).one()
    return int(count), int(size)


def owned_info(db: Session, owner_id: uuid.UUID, ids: set[str]) -> dict[str, ImageInfo]:
    """The pictures among `ids` that the person owns. Anything else is simply absent, so a document
    cannot tell a stranger's picture from a deleted one."""
    valid: list[uuid.UUID] = []
    for raw in ids:
        try:
            valid.append(uuid.UUID(raw))
        except ValueError:
            continue
    if not valid:
        return {}
    rows = db.execute(
        select(ResumeImage).where(ResumeImage.owner_user_id == owner_id, ResumeImage.id.in_(valid))
    ).scalars()
    return {
        str(r.id): ImageInfo(id=str(r.id), width=r.width, height=r.height, mime=r.mime)
        for r in rows
    }


def add_image(
    db: Session,
    *,
    owner_id: uuid.UUID,
    storage_key: str,
    mime: str,
    width: int,
    height: int,
    size_bytes: int,
    original_name: str,
    digest: str,
) -> ResumeImage | None:
    """Store a row. Returns None when the person already has this exact picture."""
    row = ResumeImage(
        owner_user_id=owner_id,
        storage_key=storage_key,
        mime=mime,
        width=width,
        height=height,
        size_bytes=size_bytes,
        original_name=original_name,
        sha256=digest,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return None
    return row


def is_used(db: Session, owner_id: uuid.UUID, image_id: uuid.UUID) -> bool:
    """Whether any of the person's resumes, or any saved version of one, still uses the picture."""
    needle = f'"image_id": "{image_id}"'
    for table in ("resume_documents", "resume_document_versions"):
        found = db.execute(
            text(
                "SELECT 1 FROM " + table + " WHERE owner_user_id = :o "  # noqa: S608
                "AND position(:n in content::text) > 0 LIMIT 1"
            ),
            {"o": owner_id, "n": needle},
        ).first()
        if found is not None:
            return True
    return False


def delete_image(db: Session, owner_id: uuid.UUID, row: ResumeImage) -> str:
    """Remove the row. Returns the storage key so the caller can delete the file."""
    key = row.storage_key
    db.execute(
        delete(ResumeImage).where(ResumeImage.id == row.id, ResumeImage.owner_user_id == owner_id)
    )
    return key
