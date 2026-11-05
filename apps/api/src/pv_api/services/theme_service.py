"""Saved themes for the resume studio: list, create, replace, delete.

Everything runs in one tenant session (Row Level Security) and filters by the signed-in owner.
A theme that belongs to someone else is "not found", never "forbidden". The rules for what a
theme may be are in pv_domain.resume_themes, the same ones the colors of a resume follow.
"""

import uuid

from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_api.schemas import ThemeIn, ThemeOut, ThemesOut
from pv_domain.failures import FailureClass
from pv_domain.resume_themes import MAX_THEMES_PER_USER, ThemeData, clean_theme
from pv_persistence.audit import record_audit
from pv_persistence.models import ResumeTheme
from pv_persistence.tenancy import tenant_session
from pv_persistence.themes import (
    add_theme,
    count_themes,
    delete_theme,
    get_theme,
    list_themes,
    update_theme,
)

TAKEN = "You already have a theme with that name. Choose another name."
FULL = f"You can keep {MAX_THEMES_PER_USER} themes. Delete one to save another."


def _not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


def _taken() -> ApiError:
    return ApiError(
        409,
        "THEME_NAME_TAKEN",
        TAKEN,
        failure_class=FailureClass.VALIDATION_FAILED,
        fields={"name": TAKEN},
    )


def _out(row: ResumeTheme) -> ThemeOut:
    return ThemeOut(
        id=row.id,
        name=row.name,
        font_pair=row.font_pair,
        accent=row.accent,
        ink=row.ink,
        muted=row.muted,
        tint=row.tint,
        updated_at=row.updated_at,
    )


def _checked(body: ThemeIn) -> ThemeData:
    data, problems = clean_theme(body.model_dump())
    if data is None:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "The theme needs a change before it can be saved.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields=problems,
        )
    return data


def list_all(engine: Engine, user_id: uuid.UUID) -> ThemesOut:
    with tenant_session(engine, user_id) as db:
        rows = list_themes(db, user_id)
        return ThemesOut(
            themes=[_out(r) for r in rows], count=len(rows), max_themes=MAX_THEMES_PER_USER
        )


def create(engine: Engine, user_id: uuid.UUID, body: ThemeIn, ip_hash: str | None) -> ThemeOut:
    data = _checked(body)
    with tenant_session(engine, user_id) as db:
        if count_themes(db, user_id) >= MAX_THEMES_PER_USER:
            raise ApiError(409, "THEME_LIMIT", FULL, failure_class=FailureClass.VALIDATION_FAILED)
        row = add_theme(db, user_id, data)
        if row is None:
            raise _taken()
        out = _out(row)
    record_audit(
        engine,
        category="audit",
        action="resume_theme.created",
        actor_user_id=user_id,
        target_type="resume_theme",
        target_id=str(out.id),
        ip_hash=ip_hash,
    )
    return out


def replace(
    engine: Engine, user_id: uuid.UUID, theme_id: uuid.UUID, body: ThemeIn, ip_hash: str | None
) -> ThemeOut:
    data = _checked(body)
    with tenant_session(engine, user_id) as db:
        row = get_theme(db, user_id, theme_id)
        if row is None:
            raise _not_found()
        if not update_theme(db, row, data):
            raise _taken()
        db.refresh(row)
        out = _out(row)
    record_audit(
        engine,
        category="audit",
        action="resume_theme.updated",
        actor_user_id=user_id,
        target_type="resume_theme",
        target_id=str(theme_id),
        ip_hash=ip_hash,
    )
    return out


def remove(engine: Engine, user_id: uuid.UUID, theme_id: uuid.UUID, ip_hash: str | None) -> None:
    with tenant_session(engine, user_id) as db:
        if get_theme(db, user_id, theme_id) is None:
            raise _not_found()
        delete_theme(db, user_id, theme_id)
    record_audit(
        engine,
        category="audit",
        action="resume_theme.deleted",
        actor_user_id=user_id,
        target_type="resume_theme",
        target_id=str(theme_id),
        ip_hash=ip_hash,
    )
