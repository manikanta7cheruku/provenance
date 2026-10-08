"""Needs a migrated PostgreSQL. Run: uv run pytest -m integration"""

from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

from pv_config import get_settings
from pv_persistence.engine import create_db_engine
from pv_persistence.health import check_readiness

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    try:
        settings = get_settings()
    except ValidationError:
        pytest.skip("No settings found. Create .env from .env.example first.")
    db_engine = create_db_engine(settings.database_url.get_secret_value())
    yield db_engine
    db_engine.dispose()


def test_readiness_is_ok_after_migration(engine: Engine) -> None:
    report = check_readiness(engine)
    assert report.database is True
    assert report.migrations == "ok"
    assert report.ready is True


def test_application_role_is_least_privilege(engine: Engine) -> None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    assert row.rolsuper is False
    assert row.rolbypassrls is False


def test_application_role_cannot_create_tables(engine: Engine) -> None:
    with engine.connect() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("CREATE TABLE must_fail (id integer)"))


def test_required_extensions_are_installed(engine: Engine) -> None:
    with engine.connect() as conn:
        names = {row[0] for row in conn.execute(text("SELECT extname FROM pg_extension"))}
    assert {"vector", "citext", "pg_trgm"} <= names
