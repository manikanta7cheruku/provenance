"""Profile entries: the first tenant-owned resource.

Authorization has two independent layers. Every query filters by the authenticated
owner here, and PostgreSQL Row Level Security enforces the same rule even if a filter
is forgotten. The client never supplies an owner.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from pv_api.deps import CurrentUser, EngineDep, WriterUser
from pv_api.errors import ApiError
from pv_api.schemas import ProfileEntryCreate, ProfileEntryOut, ProfileEntryUpdate
from pv_domain.failures import FailureClass
from pv_persistence.models import ProfileEntry
from pv_persistence.tenancy import tenant_session

router = APIRouter(prefix="/profile", tags=["profile"])


def _not_found() -> ApiError:
    # 404 for both "does not exist" and "belongs to someone else".
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


@router.get("/entries", response_model=list[ProfileEntryOut])
def list_entries(auth: CurrentUser, engine: EngineDep) -> list[ProfileEntryOut]:
    with tenant_session(engine, auth.user_id) as db:
        rows = db.execute(
            select(ProfileEntry)
            .where(ProfileEntry.owner_user_id == auth.user_id)
            .order_by(ProfileEntry.created_at)
        ).scalars()
        return [ProfileEntryOut.model_validate(row) for row in rows]


@router.post("/entries", response_model=ProfileEntryOut, status_code=201)
def create_entry(
    payload: ProfileEntryCreate, auth: WriterUser, engine: EngineDep
) -> ProfileEntryOut:
    with tenant_session(engine, auth.user_id) as db:
        entry = ProfileEntry(
            owner_user_id=auth.user_id, entry_type=payload.entry_type, data=payload.data
        )
        db.add(entry)
        db.flush()
        db.refresh(entry)
        return ProfileEntryOut.model_validate(entry)


@router.get("/entries/{entry_id}", response_model=ProfileEntryOut)
def get_entry(entry_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> ProfileEntryOut:
    with tenant_session(engine, auth.user_id) as db:
        entry = db.execute(
            select(ProfileEntry).where(
                ProfileEntry.id == entry_id, ProfileEntry.owner_user_id == auth.user_id
            )
        ).scalar_one_or_none()
        if entry is None:
            raise _not_found()
        return ProfileEntryOut.model_validate(entry)


@router.patch("/entries/{entry_id}", response_model=ProfileEntryOut)
def update_entry(
    entry_id: uuid.UUID, payload: ProfileEntryUpdate, auth: WriterUser, engine: EngineDep
) -> ProfileEntryOut:
    with tenant_session(engine, auth.user_id) as db:
        entry = db.execute(
            select(ProfileEntry).where(
                ProfileEntry.id == entry_id, ProfileEntry.owner_user_id == auth.user_id
            )
        ).scalar_one_or_none()
        if entry is None:
            raise _not_found()
        entry.data = payload.data
        entry.user_edited = True
        entry.updated_at = datetime.now(UTC)
        db.flush()
        db.refresh(entry)
        return ProfileEntryOut.model_validate(entry)


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: uuid.UUID, auth: WriterUser, engine: EngineDep) -> None:
    with tenant_session(engine, auth.user_id) as db:
        entry = db.execute(
            select(ProfileEntry).where(
                ProfileEntry.id == entry_id, ProfileEntry.owner_user_id == auth.user_id
            )
        ).scalar_one_or_none()
        if entry is None:
            raise _not_found()
        db.delete(entry)
