"""imports: batches and the per-row report, and more ways a posting can arrive

Revision ID: 0013
Revises: 0012

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  import_batches   one spreadsheet upload or one web address a person asked us to read. It holds the
                   counts and the state. `file_key` points at the uploaded file in private storage
                   and is cleared when the batch finishes, so the file does not outlive its use.
  import_items     the report: one row per spreadsheet row (or the one address), each ending as
                   created, duplicate (already saved) or rejected with a short code and a sentence.
                   It never holds posting text. `posting_id` is set to null if the posting is
                   deleted, and the report stays.
  job_postings     `acquisition_method` accepts the new ways a posting arrives: typed in, CSV, XLSX
                   and a web address. Postings stay private to their owner.

Both new tables are tenant data with Row Level Security enabled and forced.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY = """
        CREATE POLICY tenant_isolation ON {table}
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
"""


def _rls(table: str) -> None:
    op.execute("ALTER TABLE " + table + " ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE " + table + " FORCE ROW LEVEL SECURITY")
    op.execute(_POLICY.replace("{table}", table))


def upgrade() -> None:
    op.execute("ALTER TABLE job_postings DROP CONSTRAINT job_postings_acquisition_method_check")
    op.execute(
        """
        ALTER TABLE job_postings ADD CONSTRAINT job_postings_acquisition_method_check
            CHECK (acquisition_method IN (
                'user_paste', 'manual_entry', 'csv_import', 'xlsx_import', 'url_import'
            ))
        """
    )

    op.execute(
        """
        CREATE TABLE import_batches (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            kind text NOT NULL CHECK (kind IN ('csv', 'xlsx', 'url')),
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 200),
            default_source text NOT NULL CHECK (length(default_source) BETWEEN 1 AND 80),
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'done', 'failed')),
            file_key text CHECK (file_key IS NULL OR length(file_key) <= 100),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            ignored_columns jsonb NOT NULL DEFAULT '[]',
            total_rows integer NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
            created_count integer NOT NULL DEFAULT 0 CHECK (created_count >= 0),
            duplicate_count integer NOT NULL DEFAULT 0 CHECK (duplicate_count >= 0),
            rejected_count integer NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX import_batches_owner_created_idx "
        "ON import_batches (owner_user_id, created_at DESC)"
    )
    _rls("import_batches")

    op.execute(
        """
        CREATE TABLE import_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            batch_id uuid NOT NULL REFERENCES import_batches (id) ON DELETE CASCADE,
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            row_number integer NOT NULL CHECK (row_number >= 1),
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'created', 'duplicate', 'rejected')),
            code text CHECK (code IS NULL OR length(code) <= 40),
            message text CHECK (message IS NULL OR length(message) <= 300),
            title text CHECK (title IS NULL OR length(title) <= 200),
            source_url text CHECK (source_url IS NULL OR (length(source_url) <= 500
                AND source_url ~* '^https?://')),
            posting_id uuid REFERENCES job_postings (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (batch_id, row_number)
        )
        """
    )
    op.execute("CREATE INDEX import_items_posting_idx ON import_items (posting_id)")
    _rls("import_items")


def downgrade() -> None:
    op.execute("DROP TABLE import_items")
    op.execute("DROP TABLE import_batches")
    op.execute("DELETE FROM job_postings WHERE acquisition_method <> 'user_paste'")
    op.execute("ALTER TABLE job_postings DROP CONSTRAINT job_postings_acquisition_method_check")
    op.execute(
        "ALTER TABLE job_postings ADD CONSTRAINT job_postings_acquisition_method_check "
        "CHECK (acquisition_method IN ('user_paste'))"
    )
