"""SQLAlchemy engine factory."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_db_engine(url: str, *, pool_size: int = 5) -> Engine:
    """Create a pooled engine.

    pool_pre_ping drops dead connections silently. connect_timeout keeps a
    missing database from hanging a request or a health check.
    """
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=5,
        connect_args={"connect_timeout": 3},
    )
