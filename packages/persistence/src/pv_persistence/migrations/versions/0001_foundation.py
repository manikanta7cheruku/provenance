"""foundation: extensions and least-privilege grants

Revision ID: 0001
Revises:

The application role is created by infra/docker/postgres/init/01-app-role.sh
(and by CI) under the fixed name provenance_app. Every statement below is a
literal string on purpose: nothing is interpolated, so there is no string-built
SQL for a linter or a reviewer to worry about.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions the product needs later: vector search, case-insensitive email,
    # fuzzy matching for deduplication.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # The application role may use the schema but never create objects in it.
    op.execute("REVOKE CREATE ON SCHEMA public FROM provenance_app")
    op.execute("GRANT USAGE ON SCHEMA public TO provenance_app")

    # Tables and sequences created by future migrations (run by the owner) are
    # automatically readable and writable by the application role.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO provenance_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO provenance_app"
    )

    # The readiness check reads the migration version table.
    op.execute("GRANT SELECT ON alembic_version TO provenance_app")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON alembic_version FROM provenance_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM provenance_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM provenance_app"
    )
    op.execute("REVOKE USAGE ON SCHEMA public FROM provenance_app")
    # Extensions are left installed: dropping them could destroy data in later phases.
