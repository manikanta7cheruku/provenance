"""Fixtures for tests that need a migrated PostgreSQL (run with: pytest -m integration)."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import (
    PASSWORD,
    Account,
    RecordingMailer,
    generous_policies,
    make_invite,
    new_client,
    unique_email,
)
from pydantic import ValidationError
from sqlalchemy.engine import Engine

from pv_api.main import create_app
from pv_config import Settings, get_settings
from pv_domain.ratelimit import RatePolicy
from pv_persistence.engine import create_db_engine


@pytest.fixture(scope="session")
def settings() -> Settings:
    try:
        base = get_settings()
    except ValidationError:
        pytest.skip("No settings found. Create .env from .env.example first.")
    return base.model_copy(update={"signup_mode": "invite", "email_verification_required": False})


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    db_engine = create_db_engine(settings.database_url.get_secret_value())
    yield db_engine
    db_engine.dispose()


@pytest.fixture
def mailer() -> RecordingMailer:
    return RecordingMailer()


@pytest.fixture
def build_app(settings: Settings, mailer: RecordingMailer) -> Callable[..., FastAPI]:
    def _build(policies: dict[str, RatePolicy] | None = None, **overrides: Any) -> FastAPI:
        return create_app(
            settings.model_copy(update=overrides),
            rate_policies=policies or generous_policies(),
            mailer=mailer,
        )

    return _build


@pytest.fixture
def app(build_app: Callable[..., FastAPI]) -> FastAPI:
    return build_app()


@pytest.fixture
def make_account(engine: Engine) -> Callable[..., Account]:
    def _make(app: FastAPI, email: str | None = None) -> Account:
        email = email or unique_email()
        client = new_client(app)
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD, "invite_code": make_invite(engine)},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return Account(client, email, body["user"]["id"], body["csrf_token"])

    return _make
