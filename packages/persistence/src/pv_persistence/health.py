"""Readiness checks: can we reach the database, and is the schema current?"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

logger = logging.getLogger(__name__)

MigrationState = Literal["ok", "behind", "unknown"]
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@dataclass(frozen=True)
class ReadinessReport:
    database: bool
    migrations: MigrationState

    @property
    def ready(self) -> bool:
        return self.database and self.migrations == "ok"


@lru_cache(maxsize=1)
def expected_head() -> str:
    """The newest migration revision that ships with this code."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise RuntimeError("No migrations found")
    return head


def check_readiness(engine: Engine) -> ReadinessReport:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            try:
                current = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
            except ProgrammingError:
                conn.rollback()
                current = None
    except SQLAlchemyError:
        logger.warning("readiness_database_unreachable", exc_info=True)
        return ReadinessReport(database=False, migrations="unknown")
    migrations: MigrationState = "ok" if current == expected_head() else "behind"
    return ReadinessReport(database=True, migrations=migrations)
