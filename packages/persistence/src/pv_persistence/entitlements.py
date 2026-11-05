"""Plans and the usage ledger in the database.

Call everything here inside tenant_session (Row Level Security applies to the ledger and a
person's plan row). The rules (what a limit means, when the month rolls over, how to decide) are
in pv_domain.entitlements. This module reads the plans, finds a person's plan, counts what they
have used and records a billable event once.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from pv_domain.entitlements import (
    DEFAULT_PLAN,
    UNITS,
    PlanLimits,
    limits_from_row,
    period_start,
)
from pv_persistence.models import Plan, UsageLedger, UserPlan


def list_plans(db: Session) -> list[PlanLimits]:
    rows = db.execute(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order)).scalars()
    return [limits_from_row(r.id, r.label, r.data) for r in rows]


def get_plan(db: Session, plan_id: str) -> PlanLimits | None:
    row = db.execute(
        select(Plan).where(Plan.id == plan_id, Plan.active.is_(True))
    ).scalar_one_or_none()
    return limits_from_row(row.id, row.label, row.data) if row is not None else None


def plan_of(db: Session, owner_id: uuid.UUID, default_plan: str = DEFAULT_PLAN) -> PlanLimits:
    """The plan a person is on: their own row, else the default. A plan that was removed or switched
    off falls back to the default, and if even that is missing, to a plan that allows nothing, so a
    broken setup can only ever be stricter."""
    row = db.execute(
        select(UserPlan).where(UserPlan.owner_user_id == owner_id)
    ).scalar_one_or_none()
    for plan_id in ([row.plan_id] if row is not None else []) + [default_plan]:
        plan = get_plan(db, plan_id)
        if plan is not None:
            return plan
    return PlanLimits("none", "No", {u: 0 for u in UNITS}, resumes=0, exports_per_resume=0)


def assign_plan(db: Session, owner_id: uuid.UUID, plan_id: str, assigned_by: str) -> None:
    row = db.execute(
        select(UserPlan).where(UserPlan.owner_user_id == owner_id)
    ).scalar_one_or_none()
    if row is None:
        db.add(UserPlan(owner_user_id=owner_id, plan_id=plan_id, assigned_by=assigned_by[:60]))
    else:
        row.plan_id = plan_id
        row.assigned_by = assigned_by[:60]
        row.assigned_at = datetime.now(UTC)
    db.flush()


def used_by_unit(db: Session, owner_id: uuid.UUID, start: date) -> dict[str, int]:
    rows = db.execute(
        select(UsageLedger.unit, func.coalesce(func.sum(UsageLedger.amount), 0))
        .where(UsageLedger.owner_user_id == owner_id, UsageLedger.period_start == start)
        .group_by(UsageLedger.unit)
    ).all()
    counts = {unit: 0 for unit in UNITS}
    counts.update({str(unit): int(total) for unit, total in rows})
    return counts


def lock_person(db: Session, owner_id: uuid.UUID) -> None:
    """Make the check and the charge one step for this person, so two requests at once cannot both
    take the last unit. The lock is released when the transaction ends."""
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"quota:{owner_id}"})


def event_exists(db: Session, owner_id: uuid.UUID, unit: str, start: date, key: str) -> bool:
    return (
        db.execute(
            select(UsageLedger.id).where(
                UsageLedger.owner_user_id == owner_id,
                UsageLedger.unit == unit,
                UsageLedger.period_start == start,
                UsageLedger.event_key == key,
            )
        ).first()
        is not None
    )


def record_event(
    db: Session,
    *,
    owner_id: uuid.UUID,
    unit: str,
    key: str,
    plan_id: str,
    now: datetime,
    amount: int = 1,
) -> None:
    db.add(
        UsageLedger(
            owner_user_id=owner_id,
            unit=unit,
            amount=amount,
            period_start=period_start(now),
            event_key=key[:160],
            plan_id=plan_id,
        )
    )
    db.flush()


def recent_events(db: Session, owner_id: uuid.UUID, limit: int = 15) -> list[dict[str, Any]]:
    rows = db.execute(
        select(UsageLedger)
        .where(UsageLedger.owner_user_id == owner_id)
        .order_by(UsageLedger.created_at.desc())
        .limit(limit)
    ).scalars()
    return [{"unit": r.unit, "amount": r.amount, "at": r.created_at} for r in rows]
