"""Put an email on the queue, inside the caller's transaction.

The task payload has two parts: args (non-sensitive) and secret (the address and the
one-time token). The secret part is erased when the task finishes or dead-letters.
The idempotency key is derived from the token hash, so enqueueing the same token twice
cannot send two emails, and the key itself reveals nothing about the token.
"""

import uuid

from sqlalchemy.orm import Session

from pv_domain.auth import hash_token
from pv_domain.tasks import TASK_SEND_EMAIL
from pv_persistence.queue import enqueue


def enqueue_email(
    db: Session, *, template: str, to: str, token: str, owner_user_id: uuid.UUID
) -> None:
    enqueue(
        db,
        task_type=TASK_SEND_EMAIL,
        idempotency_key=f"{TASK_SEND_EMAIL}:{template}:{hash_token(token)[:32]}",
        payload={"args": {"template": template}, "secret": {"to": to, "token": token}},
        owner_user_id=owner_user_id,
        max_attempts=5,
    )
