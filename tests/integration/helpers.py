"""Shared test helpers for integration tests (a uniquely named module on purpose:
two conftest.py files cannot be imported by name without ambiguity)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_domain.auth import generate_token, hash_token
from pv_domain.ratelimit import DEFAULT_POLICIES, RatePolicy
from pv_mail import link_for, render_email
from pv_persistence.models import Invite, User

PASSWORD = "correct horse battery staple"


class RecordingMailer:
    """Reads the emails the API queued (checkpoint 1.4: the API no longer sends mail itself).

    It sees only tasks created after it was built, so tests do not see each other's mail.
    The worker must NOT be running while integration tests run (pv.ps1 itest stops it),
    otherwise it would send and erase the payloads before the test reads them.
    """

    def __init__(self, engine: Engine, base_url: str) -> None:
        self._engine = engine
        self._base_url = base_url
        with Session(engine) as db:
            self._since = db.execute(text("SELECT clock_timestamp()")).scalar_one()

    def _queued(self) -> list[tuple[str, str, str]]:
        with Session(self._engine) as db:
            rows = db.execute(
                text(
                    """
                    SELECT payload->'args'->>'template', payload->'secret'->>'to',
                           payload->'secret'->>'token'
                      FROM tasks
                     WHERE task_type = 'send_email' AND created_at >= :since
                       AND payload->'secret' IS NOT NULL
                     ORDER BY created_at, id
                    """
                ),
                {"since": self._since},
            ).all()
        return [(str(t), str(to), str(token)) for t, to, token in rows]

    @property
    def sent(self) -> list[tuple[str, str, str]]:
        result: list[tuple[str, str, str]] = []
        for template, to, token in self._queued():
            message = render_email(template, link=link_for(template, self._base_url, token))
            result.append((to, message.subject, message.body))
        return result

    def last_token_for(self, to: str) -> str:
        tokens = [token for _, recipient, token in self._queued() if recipient == to]
        assert tokens, f"no email was queued for {to}"
        return tokens[-1]


@dataclass
class Account:
    client: TestClient
    email: str
    user_id: str
    csrf_token: str

    @property
    def csrf(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf_token}


def generous_policies() -> dict[str, RatePolicy]:
    return {name: RatePolicy(name, 10_000, 60) for name in DEFAULT_POLICIES}


def random_ip() -> str:
    return ".".join(str(byte) for byte in uuid.uuid4().bytes[:4])


def new_client(app: FastAPI) -> TestClient:
    # A distinct client address per client keeps per-IP rate limits from coupling tests.
    return TestClient(app, client=(random_ip(), 50000))


def make_invite(engine: Engine, email: str | None = None) -> str:
    code = generate_token()
    with Session(engine) as db, db.begin():
        db.add(
            Invite(
                code_hash=hash_token(code),
                email=email,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
    return code


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


def promote_to_admin(engine: Engine, email: str) -> None:
    with Session(engine) as db, db.begin():
        db.execute(update(User).where(User.email == email).values(role="ADMIN"))
