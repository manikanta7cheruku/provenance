"""resume studio: documents, saved versions and PDF exports

Revision ID: 0008
Revises: 0007

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables. All three tables are tenant data
with the same Row Level Security policy as profile_entries.

  resume_documents          a resume the person builds in the studio. `content` is the structured
                            document (sections, blocks, rich text as JSON, style tokens),
                            never HTML.
                            `revision` rises on every save, so two tabs cannot overwrite each other.
                            How many a person may keep is a setting, not a constraint (FR-RES-8).
  resume_document_versions  earlier saves, so a change can be undone. Only the latest few are kept.
  resume_exports            a PDF made from one revision. The bytes live in private file storage.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
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
    op.execute(
        """
        CREATE TABLE resume_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            title text NOT NULL DEFAULT 'My resume' CHECK (length(title) BETWEEN 1 AND 120),
            content jsonb NOT NULL,
            revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (pg_column_size(content) <= 200000)
        )
        """
    )
    op.execute("CREATE INDEX resume_documents_owner_idx ON resume_documents (owner_user_id)")
    _rls("resume_documents")

    op.execute(
        """
        CREATE TABLE resume_document_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            document_id uuid NOT NULL REFERENCES resume_documents (id) ON DELETE CASCADE,
            revision integer NOT NULL CHECK (revision >= 1),
            content jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (document_id, revision)
        )
        """
    )
    _rls("resume_document_versions")

    op.execute(
        """
        CREATE TABLE resume_exports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            document_id uuid NOT NULL REFERENCES resume_documents (id) ON DELETE CASCADE,
            revision integer NOT NULL CHECK (revision >= 1),
            status text NOT NULL DEFAULT 'queued' CHECK (status IN (
                'queued', 'rendering', 'ready', 'failed'
            )),
            storage_key text CHECK (storage_key IS NULL OR length(storage_key) <= 80),
            size_bytes integer CHECK (size_bytes IS NULL OR size_bytes >= 0),
            page_count integer CHECK (page_count IS NULL OR page_count >= 1),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX resume_exports_owner_created_idx "
        "ON resume_exports (owner_user_id, created_at DESC)"
    )
    _rls("resume_exports")


def downgrade() -> None:
    op.execute("DROP TABLE resume_exports")
    op.execute("DROP TABLE resume_document_versions")
    op.execute("DROP TABLE resume_documents")
