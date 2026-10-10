"""Tenant context for Row Level Security.

The API sets app.user_id for the duration of ONE transaction. set_config(..., true)
is the parameterized form of SET LOCAL: the value disappears at commit or rollback,
so a pooled connection can never carry one user's identity into another request.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def set_tenant(session: Session, user_id: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)})


@contextmanager
def tenant_session(engine: Engine, user_id: uuid.UUID) -> Iterator[Session]:
    """A session whose single transaction is scoped to one tenant. Commits on success."""
    with Session(engine, expire_on_commit=False) as session, session.begin():
        set_tenant(session, user_id)
        yield session
