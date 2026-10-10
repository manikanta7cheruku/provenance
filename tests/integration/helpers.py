"""Shared test helpers for integration tests (a uniquely named module on purpose:
two conftest.py files cannot be imported by name without ambiguity)."""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_domain.auth import generate_token, hash_token
from pv_domain.ratelimit import DEFAULT_POLICIES, RatePolicy
from pv_persistence.models import Invite, User

PASSWORD = "correct horse battery staple"


class RecordingMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))

    def last_token_for(self, to: str) -> str:
        bodies = [body for recipient, _, body in self.sent if recipient == to]
        assert bodies, f"no email was sent to {to}"
        match = re.search(r"token=([A-Za-z0-9_-]+)", bodies[-1])
        assert match, "no token link in the email"
        return match.group(1)


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
