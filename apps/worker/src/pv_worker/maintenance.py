"""Housekeeping the worker does on a timer, so nobody has to remember to.

  sweep_reports      remove expired reports (and any beyond the newest 20 per person) and delete
                     their files (C-137). Reports are a person's own rows, so each person is visited
                     in turn with their own tenant set, a few hundred per transaction.
  sweep_closed_jobs  delete job listings fetched from sources that were closed more than
                     CLOSED_JOB_RETENTION_DAYS ago (C-53). A person's own saved jobs are separate
                     rows and are never touched. Links to a deleted listing go with it.
  deliver_alerts     email the administrators about alerts that are new, or still there after the
                     cooldown (C-141). Off unless ALERT_EMAIL_ENABLED is true.

Every function is safe to run twice and does nothing when there is nothing to do. A failure in one
is logged and does not stop the others or the worker.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_domain.alerts import Thresholds, evaluate, plan_delivery, render_digest
from pv_domain.report import KEEP_EXPORTS
from pv_files import FileStorage, StorageError
from pv_mail import MailDeliveryError, Mailer
from pv_persistence import alert_deliveries
from pv_persistence.models import User
from pv_persistence.reports import expire_reports
from pv_persistence.snapshot import build_snapshot
from pv_persistence.tenancy import set_tenant

logger = logging.getLogger("pv_worker.maintenance")

BATCH = 300


def sweep_reports(engine: Engine, storage: FileStorage) -> tuple[int, int]:
    """(reports removed, files deleted)."""
    with Session(engine) as db:
        user_ids: list[uuid.UUID] = list(db.execute(select(User.id)).scalars())
    removed = files = 0
    for start in range(0, len(user_ids), BATCH):
        keys: list[str] = []
        with Session(engine, expire_on_commit=False) as db, db.begin():
            for user_id in user_ids[start : start + BATCH]:
                set_tenant(db, user_id)
                keys += expire_reports(db, user_id, KEEP_EXPORTS)
        # The rows are gone for good. A file that cannot be deleted now is retried never, so it is
        # logged: an orphan costs disk, not privacy, because nothing refers to its key.
        for key in keys:
            removed += 1
            try:
                storage.delete(key)
                files += 1
            except StorageError:
                logger.warning("report_file_not_deleted", extra={"key_prefix": key[:8]})
    return removed, files


def sweep_closed_jobs(engine: Engine, days: int) -> int:
    """How many closed listings were deleted."""
    with Session(engine) as db, db.begin():
        result = db.execute(
            text(
                "DELETE FROM source_jobs WHERE closed_at IS NOT NULL AND closed_at < now() - make_interval(days => :d)"
            ),
            {"d": days},
        )
        return int(getattr(result, "rowcount", 0) or 0)


def deliver_alerts(
    engine: Engine, settings: Settings, mailer: Mailer, now: datetime | None = None
) -> int:
    """How many alerts were emailed. A record is kept only after the mail was handed over, so a mail
    server that is down means the same alerts are tried again on the next round."""
    moment = now or datetime.now(UTC)
    alerts = evaluate(
        build_snapshot(engine, now=moment),
        Thresholds(daily_spend_ceiling_usd=settings.llm_daily_spend_ceiling_usd),
    )
    cooldown = timedelta(hours=settings.alert_email_cooldown_hours)
    with Session(engine) as db:
        plan = plan_delivery(alerts, alert_deliveries.sent_alerts(db), moment, cooldown)
        recipients = alert_deliveries.administrator_emails(db)
    with Session(engine) as db, db.begin():
        alert_deliveries.clear(db, plan.clear)
    if not plan.send or not recipients:
        return 0
    subject, body = render_digest(plan.send, settings.public_base_url)
    delivered = 0
    for address in recipients:
        try:
            mailer.send(address, subject, body)
            delivered += 1
        except MailDeliveryError:
            logger.warning("alert_mail_not_delivered")
    if delivered:
        with Session(engine) as db, db.begin():
            alert_deliveries.record_sent(db, plan.send, moment)
        return len(plan.send)
    return 0


def run_maintenance(
    engine: Engine, settings: Settings, mailer: Mailer, storage: FileStorage, *, hourly: bool
) -> dict[str, int]:
    """One round. `hourly` also runs the sweeps that visit every person."""
    done: dict[str, int] = {}
    steps: list[tuple[str, object]] = []
    if hourly:
        steps.append(("reports_removed", lambda: sweep_reports(engine, storage)[0]))
        steps.append(
            (
                "closed_jobs_deleted",
                lambda: sweep_closed_jobs(engine, settings.closed_job_retention_days),
            )
        )
    if settings.alert_email_enabled:
        steps.append(("alerts_emailed", lambda: deliver_alerts(engine, settings, mailer)))
    for name, step in steps:
        try:
            done[name] = step()  # type: ignore[operator]
        except Exception:  # noqa: BLE001 - one failing step must not stop the others
            logger.error("maintenance_step_failed", extra={"step": name}, exc_info=True)
    logger.info("maintenance_done", extra={"done": done})
    return done
