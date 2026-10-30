"""The profile: entries (what the person has done) and preferences (what they are looking for).

Authorization has two independent layers. Every query filters by the authenticated
owner here, and PostgreSQL Row Level Security enforces the same rule even if a filter
is forgotten. The client never supplies an owner.

Entries are validated against the specs in pv_domain.profile, the same rules the resume
parser applies, so a hand-typed entry and a parsed one are held to one standard.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from pv_api.deps import CurrentUser, EngineDep, WriterUser
from pv_api.errors import ApiError
from pv_api.schemas import (
    EntrySpecOut,
    PreferencesIn,
    PreferencesOut,
    ProfileEntryCreate,
    ProfileEntryOut,
    ProfileEntryUpdate,
)
from pv_domain.failures import FailureClass
from pv_domain.profile import flagged_fields, specs_as_dicts, validate_entry
from pv_persistence.evidence import sync_evidence
from pv_persistence.models import ProfileEntry, ProfilePreferences
from pv_persistence.resumes import list_entries
from pv_persistence.tenancy import tenant_session

router = APIRouter(prefix="/profile", tags=["profile"])


def _not_found() -> ApiError:
    # 404 for both "does not exist" and "belongs to someone else".
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


def _out(entry: ProfileEntry) -> ProfileEntryOut:
    out = ProfileEntryOut.model_validate(entry)
    out.flags = flagged_fields(entry.entry_type, entry.data)
    return out


def _checked(entry_type: str, data: dict[str, object]) -> dict[str, object]:
    check = validate_entry(entry_type, data)
    if check.errors:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields=check.errors,
        )
    return check.clean


@router.get("/schema", response_model=list[EntrySpecOut])
def entry_schema(auth: CurrentUser) -> list[dict[str, object]]:
    """The fields of every entry type. The browser draws its forms from this."""
    return specs_as_dicts()


@router.get("/entries", response_model=list[ProfileEntryOut])
def get_entries(auth: CurrentUser, engine: EngineDep) -> list[ProfileEntryOut]:
    with tenant_session(engine, auth.user_id) as db:
        return [_out(entry) for entry in list_entries(db, auth.user_id)]


@router.post("/entries", response_model=ProfileEntryOut, status_code=201)
def create_entry(
    payload: ProfileEntryCreate, auth: WriterUser, engine: EngineDep
) -> ProfileEntryOut:
    clean = _checked(payload.entry_type, payload.data)
    with tenant_session(engine, auth.user_id) as db:
        position = max((e.position for e in list_entries(db, auth.user_id)), default=-1) + 1
        entry = ProfileEntry(
            owner_user_id=auth.user_id,
            entry_type=payload.entry_type,
            data=clean,
            source="user",
            position=position,
        )
        db.add(entry)
        db.flush()
        db.refresh(entry)
        sync_evidence(db, auth.user_id)
        return _out(entry)


def _load(db_entries: list[ProfileEntry], entry_id: uuid.UUID) -> ProfileEntry:
    for entry in db_entries:
        if entry.id == entry_id:
            return entry
    raise _not_found()


@router.get("/entries/{entry_id}", response_model=ProfileEntryOut)
def get_entry(entry_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> ProfileEntryOut:
    with tenant_session(engine, auth.user_id) as db:
        return _out(_load(list_entries(db, auth.user_id), entry_id))


@router.patch("/entries/{entry_id}", response_model=ProfileEntryOut)
def update_entry(
    entry_id: uuid.UUID, payload: ProfileEntryUpdate, auth: WriterUser, engine: EngineDep
) -> ProfileEntryOut:
    with tenant_session(engine, auth.user_id) as db:
        entry = _load(list_entries(db, auth.user_id), entry_id)
        entry.data = _checked(entry.entry_type, payload.data)
        entry.user_edited = True
        entry.updated_at = datetime.now(UTC)
        db.flush()
        db.refresh(entry)
        sync_evidence(db, auth.user_id)
        return _out(entry)


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: uuid.UUID, auth: WriterUser, engine: EngineDep) -> None:
    with tenant_session(engine, auth.user_id) as db:
        db.delete(_load(list_entries(db, auth.user_id), entry_id))
        db.flush()  # the database trigger removes the entry's chunk
        sync_evidence(db, auth.user_id)


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(auth: CurrentUser, engine: EngineDep) -> PreferencesOut:
    with tenant_session(engine, auth.user_id) as db:
        row = db.execute(
            select(ProfilePreferences).where(ProfilePreferences.owner_user_id == auth.user_id)
        ).scalar_one_or_none()
        return PreferencesOut.model_validate(row) if row else PreferencesOut()


@router.put("/preferences", response_model=PreferencesOut)
def put_preferences(payload: PreferencesIn, auth: WriterUser, engine: EngineDep) -> PreferencesOut:
    with tenant_session(engine, auth.user_id) as db:
        row = db.execute(
            select(ProfilePreferences).where(ProfilePreferences.owner_user_id == auth.user_id)
        ).scalar_one_or_none()
        if row is None:
            row = ProfilePreferences(owner_user_id=auth.user_id)
            db.add(row)
        for name, value in payload.model_dump().items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        db.flush()
        db.refresh(row)
        return PreferencesOut.model_validate(row)
