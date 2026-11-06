"""account deletion

Revision ID: 0023
Revises: 0022

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  users.deletion_requested_at  set when a person asks to delete their account. From then on the
                               account is inactive and cannot sign in. The row itself is removed by
                               the deletion task, which also cascades every table that holds the
                               person's data.
  account_deletions            a minimal, non-personal record that a deletion happened: when it was
                               asked for, when it finished, how many stored files and how many
                               stray rows were removed. It holds no user id, no email and nothing
                               that could be traced back to a person. A system table.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN deletion_requested_at timestamptz")
    op.execute(
        """
        CREATE TABLE account_deletions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            requested_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            completed_at timestamptz,
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'done', 'failed')),
            files_removed integer NOT NULL DEFAULT 0 CHECK (files_removed >= 0),
            stray_rows_removed integer NOT NULL DEFAULT 0 CHECK (stray_rows_removed >= 0),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40)
        )
        """
    )
    op.execute(
        "CREATE INDEX account_deletions_status_idx ON account_deletions (status, requested_at)"
    )
    op.execute("REVOKE DELETE ON account_deletions FROM provenance_app")


def downgrade() -> None:
    op.execute("DROP TABLE account_deletions")
    op.execute("ALTER TABLE users DROP COLUMN deletion_requested_at")
