"""Alembic environment. Always runs as the database OWNER role.

Models do not exist yet (checkpoint 1.2 adds them), so there is no autogenerate
metadata. Migrations are written by hand on purpose: you review every statement.
"""

from alembic import context
from sqlalchemy import create_engine, pool

from pv_config import get_settings

target_metadata = None


def run_migrations_offline() -> None:
    url = get_settings().migration_database_url.get_secret_value()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_settings().migration_database_url.get_secret_value()
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
