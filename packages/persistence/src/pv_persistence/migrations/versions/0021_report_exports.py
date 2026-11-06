"""report exports

Revision ID: 0021
Revises: 0020

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  report_exports  one row per report a person asked for: its format, the filters that chose the
                  jobs, the state of the work, where the finished file is in private storage, and
                  when it expires. The file itself is never in the database.

Tenant data with Row Level Security enabled and forced. It goes with the person.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE report_exports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            kind text NOT NULL DEFAULT 'opportunities' CHECK (kind IN ('opportunities')),
            format text NOT NULL CHECK (format IN ('csv', 'xlsx', 'docx')),
            params jsonb NOT NULL DEFAULT '{}'::jsonb,
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'building', 'ready', 'failed')),
            storage_key text,
            size_bytes integer CHECK (size_bytes IS NULL OR size_bytes >= 0),
            row_count integer CHECK (row_count IS NULL OR row_count >= 0),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            expires_at timestamptz NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX report_exports_owner_created_idx "
        "ON report_exports (owner_user_id, created_at DESC)"
    )
    op.execute("ALTER TABLE report_exports ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE report_exports FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON report_exports
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE report_exports")
