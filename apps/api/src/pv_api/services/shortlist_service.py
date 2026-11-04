"""The shortlist email: the person's schedule, a preview of what would be sent, and "send one now".

Everything runs in one tenant session (Row Level Security) for the signed-in person. The email is off
until they turn it on, goes only to a verified address, and is built by the same function the worker
uses (pv_persistence.shortlist.compute_shortlist), so the preview is exactly what an email would hold.
The API queues the work. The worker sends.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_api.schemas import (
    ShortlistItemOut,
    ShortlistOut,
    ShortlistPreviewOut,
    ShortlistRunOut,
    ShortlistSendOut,
    ShortlistSettingsIn,
    ShortlistSettingsOut,
)
from pv_config import Settings
from pv_domain.failures import FailureClass
from pv_domain.shortlist import (
    DEFAULT_ITEMS,
    NOT_VERIFIED_MESSAGE,
    Schedule,
    ScheduleError,
    clean_schedule,
    describe_schedule,
)
from pv_domain.tasks import TASK_SEND_SHORTLIST
from pv_mail import delivery_hint
from pv_persistence.audit import record_audit
from pv_persistence.models import ShortlistRun, ShortlistSettings, User
from pv_persistence.queue import enqueue
from pv_persistence.shortlist import (
    compute_shortlist,
    get_settings,
    recent_runs,
    save_settings,
    schedule_of,
)
from pv_persistence.tenancy import tenant_session

_OUTCOME_TEXT = {
    "sent": "Sent",
    "nothing": "Nothing to send: no job was worth a look that you had not seen",
    "skipped": "Not sent: your email address is not verified",
    "failed": "Could not be sent. The next one is still scheduled",
}


def _verified(db, user_id: uuid.UUID) -> bool:  # type: ignore[no-untyped-def]
    user = db.get(User, user_id)
    return bool(user and user.is_active and user.email_verified_at is not None)


def _settings_out(row: ShortlistSettings | None) -> ShortlistSettingsOut:
    schedule = schedule_of(row) if row else Schedule()
    return ShortlistSettingsOut(
        enabled=bool(row and row.enabled),
        frequency=schedule.frequency,  # type: ignore[arg-type]
        weekday=schedule.weekday,
        hour=schedule.hour,
        timezone=schedule.timezone,
        max_items=schedule.max_items,
        schedule_text=describe_schedule(schedule),
        next_run_at=row.next_run_at if row else None,
        last_run_at=row.last_run_at if row else None,
    )


def _run_out(run: ShortlistRun) -> ShortlistRunOut:
    return ShortlistRunOut(
        outcome=run.outcome,  # type: ignore[arg-type]
        outcome_text=_OUTCOME_TEXT.get(run.outcome, run.outcome),
        item_count=run.item_count,
        manual=run.manual,
        at=run.created_at,
    )


def view(engine: Engine, app_settings: Settings, user_id: uuid.UUID) -> ShortlistOut:
    with tenant_session(engine, user_id) as db:
        verified = _verified(db, user_id)
        return ShortlistOut(
            settings=_settings_out(get_settings(db, user_id)),
            runs=[_run_out(r) for r in recent_runs(db, user_id)],
            email_verified=verified,
            blocker=None if verified else NOT_VERIFIED_MESSAGE,
            delivery_note=delivery_hint(app_settings).text,
        )


def save(
    engine: Engine,
    app_settings: Settings,
    user_id: uuid.UUID,
    payload: ShortlistSettingsIn,
    ip_hash: str | None,
) -> ShortlistOut:
    try:
        schedule = clean_schedule(payload.model_dump())
    except ScheduleError as error:
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED, fields=error.fields,
        ) from error  # fmt: skip
    with tenant_session(engine, user_id) as db:
        if payload.enabled and not _verified(db, user_id):
            raise ApiError(
                409, "EMAIL_NOT_VERIFIED", NOT_VERIFIED_MESSAGE,
                failure_class=FailureClass.USER_ACTION_REQUIRED,
            )  # fmt: skip
        save_settings(db, user_id, schedule, enabled=payload.enabled, now=datetime.now(UTC))
    record_audit(
        engine, category="audit", action="shortlist.settings_changed", actor_user_id=user_id,
        ip_hash=ip_hash,
        metadata={"enabled": payload.enabled, "frequency": schedule.frequency},
    )  # fmt: skip
    return view(engine, app_settings, user_id)


def preview(engine: Engine, user_id: uuid.UUID) -> ShortlistPreviewOut:
    """What an email would hold if it were sent now. Nothing is sent and nothing is recorded."""
    with tenant_session(engine, user_id) as db:
        settings = get_settings(db, user_id)
        limit = settings.max_items if settings else DEFAULT_ITEMS
        chosen = compute_shortlist(db, user_id, limit)
    items = [
        ShortlistItemOut(
            id=uuid.UUID(c.id),
            title=c.title or None,
            company=c.company or None,
            location=c.location or None,
            band=c.band,
            eligibility=c.eligibility,
            reason=reason,
        )
        for c, reason in chosen
    ]
    note = (
        "These are the jobs that would be in an email now."
        if items
        else "Nothing would be sent now. A job needs a finished evidence check, a Strong or Good "
        "fit, nothing in the way, and not to have been in an earlier email."
    )
    return ShortlistPreviewOut(items=items, note=note)


def send_now(engine: Engine, user_id: uuid.UUID, ip_hash: str | None) -> ShortlistSendOut:
    now = datetime.now(UTC)
    with tenant_session(engine, user_id) as db:
        if not _verified(db, user_id):
            raise ApiError(
                409, "EMAIL_NOT_VERIFIED", NOT_VERIFIED_MESSAGE,
                failure_class=FailureClass.USER_ACTION_REQUIRED,
            )  # fmt: skip
        enqueue(
            db,
            task_type=TASK_SEND_SHORTLIST,
            idempotency_key=f"{TASK_SEND_SHORTLIST}:{user_id}:manual:{now.isoformat()}",
            payload={"args": {"slot": now.isoformat(), "manual": True}},
            owner_user_id=user_id,
            max_attempts=3,
        )
    record_audit(
        engine, category="audit", action="shortlist.send_requested", actor_user_id=user_id,
        ip_hash=ip_hash,
    )  # fmt: skip
    return ShortlistSendOut(
        queued=True,
        message="Queued. If anything is worth a look it will arrive shortly. If not, the list below says so.",
    )
