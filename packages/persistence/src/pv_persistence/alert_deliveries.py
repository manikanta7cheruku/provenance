"""Which alerts have been emailed, and when. A system table with no person in it."""

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from pv_domain.alerts import Alert


def sent_alerts(db: Session) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    for key, moment in db.execute(text("SELECT alert_key, last_sent_at FROM alert_deliveries")):
        if isinstance(moment, datetime):
            out[str(key)] = moment
    return out


def record_sent(db: Session, alerts: tuple[Alert, ...], now: datetime | None = None) -> None:
    moment = now or datetime.now(UTC)
    for alert in alerts:
        db.execute(
            text(
                "INSERT INTO alert_deliveries (alert_key, severity, first_sent_at, last_sent_at) "
                "VALUES (:k, :s, :t, :t) ON CONFLICT (alert_key) DO UPDATE SET "
                "last_sent_at = :t, severity = :s, times_sent = alert_deliveries.times_sent + 1"
            ),
            {"k": alert.key[:120], "s": alert.severity, "t": moment},
        )


def clear(db: Session, keys: tuple[str, ...]) -> None:
    for key in keys:
        db.execute(text("DELETE FROM alert_deliveries WHERE alert_key = :k"), {"k": key})


def administrator_emails(db: Session) -> list[str]:
    emails: list[str] = []
    for (email,) in db.execute(
        text("SELECT email FROM users WHERE role = 'ADMIN' AND is_active ORDER BY created_at")
    ):
        emails.append(str(email))
    return emails
