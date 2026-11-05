"""Saved themes for the resume studio.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner. What a theme is allowed to be is decided in pv_domain.resume_themes.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pv_domain.resume_themes import ThemeData
from pv_persistence.models import ResumeTheme


def list_themes(db: Session, owner_id: uuid.UUID) -> list[ResumeTheme]:
    return list(
        db.execute(
            select(ResumeTheme)
            .where(ResumeTheme.owner_user_id == owner_id)
            .order_by(func.lower(ResumeTheme.name), ResumeTheme.id)
        ).scalars()
    )


def get_theme(db: Session, owner_id: uuid.UUID, theme_id: uuid.UUID) -> ResumeTheme | None:
    return db.execute(
        select(ResumeTheme).where(ResumeTheme.owner_user_id == owner_id, ResumeTheme.id == theme_id)
    ).scalar_one_or_none()


def count_themes(db: Session, owner_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(ResumeTheme)
            .where(ResumeTheme.owner_user_id == owner_id)
        ).scalar_one()
    )


def add_theme(db: Session, owner_id: uuid.UUID, data: ThemeData) -> ResumeTheme | None:
    """Store a theme. Returns None when the person already has one with this name."""
    row = ResumeTheme(
        owner_user_id=owner_id,
        name=data.name,
        font_pair=data.font_pair,
        accent=data.accent,
        ink=data.ink,
        muted=data.muted,
        tint=data.tint,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return None
    return row


def update_theme(db: Session, row: ResumeTheme, data: ThemeData) -> bool:
    """Replace a theme. Returns False when the new name is taken by another theme."""
    try:
        with db.begin_nested():
            row.name = data.name
            row.font_pair = data.font_pair
            row.accent = data.accent
            row.ink = data.ink
            row.muted = data.muted
            row.tint = data.tint
            row.updated_at = func.now()
            db.flush()
    except IntegrityError:
        return False
    return True


def delete_theme(db: Session, owner_id: uuid.UUID, theme_id: uuid.UUID) -> None:
    db.execute(
        delete(ResumeTheme).where(ResumeTheme.id == theme_id, ResumeTheme.owner_user_id == owner_id)
    )
