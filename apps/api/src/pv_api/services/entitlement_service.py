"""Quotas for the API: may this person do this billable thing now, and what have they used?

`charge` is called from the start of every billable action, inside the same transaction that queues the
work, so the check, the charge and the queueing succeed or fail together. A refusal is a structured
QUOTA_EXCEEDED error (HTTP 429) that says what was used, what the plan allows and when the month starts
again, in one plain sentence, plus the same facts as data so a screen can show them.

What it guarantees:
  - the same event key in the same month is charged once (a retry, or checking the same job twice);
  - two requests at once cannot both take the last unit (the person is locked for the check and charge);
  - an exhausted quota never blocks anything that is free: reading, editing, exporting what you have;
  - a missing or broken plan can only ever be stricter, never more generous.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    PaymentsOut,
    PlanChoiceOut,
    PlanOut,
    QuotaOut,
    UsageEventOut,
)
from pv_config import Settings
from pv_domain.entitlements import (
    UNIT_HELP,
    UNIT_LABELS,
    UNITS,
    PlanLimits,
    decide,
    meter_state,
    next_reset,
    percent,
    period_start,
    quota_message,
)
from pv_domain.failures import FailureClass
from pv_persistence.entitlements import (
    event_exists,
    list_plans,
    lock_person,
    plan_of,
    recent_events,
    record_event,
    used_by_unit,
)
from pv_persistence.models import ResumeDocument
from pv_persistence.tenancy import tenant_session

PAYMENTS_MESSAGE = (
    "Paid plans are not available yet. Nothing is charged and nothing is collected. "
    "The limits on your plan are shown below."
)


def plan_for(db: Session, settings: Settings, user_id: uuid.UUID) -> PlanLimits:
    return plan_of(db, user_id, settings.default_plan)


def charge(
    db: Session,
    settings: Settings,
    user_id: uuid.UUID,
    unit: str,
    key: str,
    *,
    now: datetime | None = None,
) -> None:
    """Take one unit, or refuse with QUOTA_EXCEEDED. Call it inside the tenant session that queues the
    work. The same key in the same month is the same event and costs nothing more."""
    now = now or datetime.now(UTC)
    lock_person(db, user_id)
    start = period_start(now)
    if event_exists(db, user_id, unit, start, key):
        return
    plan = plan_for(db, settings, user_id)
    limit = plan.units.get(unit, 0)
    used = used_by_unit(db, user_id, start)[unit]
    decision = decide(limit, used)
    if not decision.allowed and limit is not None:  # an unlimited plan is always allowed
        resets = next_reset(now)
        raise ApiError(
            429,
            "QUOTA_EXCEEDED",
            quota_message(unit, plan.label, used, limit, resets),
            failure_class=FailureClass.QUOTA_EXCEEDED,
            details={
                "unit": unit,
                "used": used,
                "limit": limit,
                "plan": plan.id,
                "resets_at": resets.isoformat(),
            },
        )
    record_event(db, owner_id=user_id, unit=unit, key=key, plan_id=plan.id, now=now)


def resume_cap(db: Session, settings: Settings, user_id: uuid.UUID) -> tuple[int, str]:
    """How many resumes the person's plan keeps, and the plan's name."""
    plan = plan_for(db, settings, user_id)
    return plan.resumes, plan.label


def exports_cap(db: Session, settings: Settings, user_id: uuid.UUID) -> int:
    return plan_for(db, settings, user_id).exports_per_resume


def _quota(unit: str, plan: PlanLimits, used: int) -> QuotaOut:
    label, noun = UNIT_LABELS[unit]
    limit = plan.units.get(unit, 0)
    return QuotaOut(
        unit=unit,
        label=label,
        noun=noun,
        help=UNIT_HELP[unit],
        used=used,
        limit=limit,
        remaining=None if limit is None else max(0, limit - used),
        percent=percent(limit, used),
        state=meter_state(limit, used),
    )


def view(engine: Engine, settings: Settings, user_id: uuid.UUID) -> PlanOut:
    now = datetime.now(UTC)
    with tenant_session(engine, user_id) as db:
        plan = plan_for(db, settings, user_id)
        start = period_start(now)
        used = used_by_unit(db, user_id, start)
        resumes = int(
            db.execute(
                select(func.count())
                .select_from(ResumeDocument)
                .where(ResumeDocument.owner_user_id == user_id)
            ).scalar_one()
        )
        events: list[dict[str, Any]] = recent_events(db, user_id)
        choices = [
            PlanChoiceOut(
                id=p.id,
                label=p.label,
                current=p.id == plan.id,
                limits={u: p.units.get(u) for u in UNITS},
                resumes=p.resumes,
                exports_per_resume=p.exports_per_resume,
            )
            for p in list_plans(db)
        ]
    return PlanOut(
        plan_id=plan.id,
        plan_label=plan.label,
        period_start=start,
        resets_at=next_reset(now),
        quotas=[_quota(u, plan, used[u]) for u in UNITS],
        resumes_used=resumes,
        resumes_limit=plan.resumes,
        exports_per_resume=plan.exports_per_resume,
        plans=choices,
        recent=[
            UsageEventOut(label=UNIT_LABELS[e["unit"]][0], amount=e["amount"], at=e["at"])
            for e in events
            if e["unit"] in UNIT_LABELS
        ],
        payments=PaymentsOut(enabled=False, message=PAYMENTS_MESSAGE),
        provisional=True,
    )


def upgrade_unavailable() -> ApiError:
    """Paid plans exist as an interface only. Asking to change plan says so and changes nothing."""
    return ApiError(
        409,
        "PAYMENTS_NOT_AVAILABLE",
        PAYMENTS_MESSAGE,
        failure_class=FailureClass.USER_ACTION_REQUIRED,
    )
