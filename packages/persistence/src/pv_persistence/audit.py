"""Append-only audit and security events. Written in their own transaction,
so a rolled-back request still leaves its audit record."""

import uuid
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_persistence.models import AuditEvent


def record_audit(
    engine: Engine,
    *,
    category: str,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_hash: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    with Session(engine) as session, session.begin():
        session.add(
            AuditEvent(
                category=category,
                action=action,
                actor_user_id=actor_user_id,
                target_type=target_type,
                target_id=target_id,
                ip_hash=ip_hash,
                event_metadata=metadata or {},
            )
        )
