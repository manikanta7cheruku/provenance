"""Send one person's shortlist email, and arrange the next one.

The task schedules its own next run, like polling a source, so the email continues for as long as the
person keeps it on. The rules, none of which the caller can switch off:

  - the task is for one due time (its slot). If the person turned the email off, or changed the
    schedule so that time is no longer the next one, the task does nothing and queues nothing
  - a due time is handled once: a run row is unique per person and time, so a retried task cannot
    record or send it twice
  - the email goes only to a verified address. An unverified address is a recorded "skipped"
  - what is sent comes from pv_persistence.shortlist.compute_shortlist: deterministic, with each
    job's reason, never a job sent before. Nothing to send is a recorded "nothing", not an empty email
  - mail trouble that may pass is retried. On the last attempt the run is recorded as failed and the
    next time is still queued, so one bad day does not end the email
  - the next time is worked out on the person's own clock from now (or the due time if later), so a
    worker that was down does not send a pile of old emails when it comes back

The address is read from the account here and is never put in a task payload. Email cannot be made
perfectly idempotent: if the worker dies after the mail server accepted the message but before the run
was recorded, the retry sends a duplicate. That is the price of at-least-once delivery.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pv_domain.shortlist import describe_schedule, next_run
from pv_mail import MailDeliveryError, ShortlistItem, render_shortlist
from pv_persistence.models import ShortlistSettings, User
from pv_persistence.shortlist import (
    arm,
    compute_shortlist,
    get_run,
    get_settings,
    record_run,
    schedule_of,
)
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure


def handle_send_shortlist(ctx: TaskContext) -> None:
    run_send(ctx)


def _parse_slot(value: object) -> datetime:
    if not isinstance(value, str):
        raise TaskFailure("Invalid shortlist task arguments.", retryable=False)
    try:
        slot = datetime.fromisoformat(value)
    except ValueError as exc:
        raise TaskFailure("Invalid shortlist task arguments.", retryable=False) from exc
    if slot.tzinfo is None:
        raise TaskFailure("Invalid shortlist task arguments.", retryable=False)
    return slot.astimezone(UTC)


def run_send(ctx: TaskContext) -> None:
    owner = ctx.owner_user_id
    if owner is None:
        raise TaskFailure("The shortlist task has no owner.", retryable=False)
    slot = _parse_slot(ctx.args.get("slot"))
    manual = bool(ctx.args.get("manual"))
    now = datetime.now(UTC)

    with tenant_session(ctx.engine, owner) as db:
        settings = get_settings(db, owner)
        if not manual and (
            settings is None or not settings.enabled or settings.next_run_at != slot
        ):
            return  # turned off, or the schedule changed: this time is no longer the next one
        if get_run(db, owner, slot) is not None:
            if not manual and settings is not None:
                _arm_next(db, owner, settings, slot, now)
            return  # already handled: a retry must not send it again
        user = db.get(User, owner)
        verified = bool(user and user.is_active and user.email_verified_at is not None)
        address = user.email if user else ""
        schedule = schedule_of(settings) if settings else None
        limit = schedule.max_items if schedule else 5
        chosen = compute_shortlist(db, owner, limit) if verified else []

    items = [
        ShortlistItem(
            title=c.title,
            company=c.company,
            place=c.location,
            reason=reason,
            url=f"{ctx.settings.public_base_url.rstrip('/')}/opportunities/{c.id}",
        )
        for c, reason in chosen
    ]
    outcome, error = ("skipped" if not verified else "nothing" if not items else "sent"), None
    if items:
        message = render_shortlist(
            items,
            schedule_text=describe_schedule(schedule) if schedule else "On request",
            settings_url=f"{ctx.settings.public_base_url.rstrip('/')}/settings",
        )
        try:
            ctx.mailer.send(address, message.subject, message.body)
        except MailDeliveryError as exc:
            if exc.retryable and ctx.attempt < ctx.max_attempts:
                raise TaskFailure(exc.summary, retryable=True) from exc
            outcome, error = "failed", "mail_failed"

    with tenant_session(ctx.engine, owner) as db:
        record_run(
            db,
            owner_id=owner,
            slot=slot,
            outcome=outcome,
            posting_ids=[uuid.UUID(c.id) for c, _ in chosen] if outcome == "sent" else [],
            manual=manual,
            error_code=error,
        )
        settings = get_settings(db, owner)
        if settings is not None:
            settings.last_run_at = now
            if not manual and settings.enabled and settings.next_run_at == slot:
                _arm_next(db, owner, settings, slot, now)


def _arm_next(
    db: Session, owner: uuid.UUID, settings: ShortlistSettings, slot: datetime, now: datetime
) -> None:
    after = max(slot, now)
    following = next_run(after, schedule_of(settings))
    settings.next_run_at = following
    db.flush()
    arm(db, owner, following, now)
