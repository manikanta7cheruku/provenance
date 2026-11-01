"""resume tailoring: one run per resume and job, and the suggestions it made

Revision ID: 0009
Revises: 0008

Every statement is a literal string (no f-strings). Both tables are tenant data with the same Row
Level Security policy as the rest.

  resume_tailorings      one per resume and posting. `seq` rises when it is started again, so a task
                         for an older start does nothing. It never holds resume text.
  tailoring_suggestions  one proposed rewording of one part of the resume. It keeps the old and
                         new lines, the reason, the evidence it cites and the result of the
                         grounding check (every claim and whether it was found), so the person can
                         see why it is blocked or fine. `status` records the person's decision.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
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
        CREATE TABLE resume_tailorings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            document_id uuid NOT NULL REFERENCES resume_documents (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            status text NOT NULL DEFAULT 'queued' CHECK (status IN (
                'queued', 'working', 'ready', 'failed'
            )),
            seq integer NOT NULL DEFAULT 1 CHECK (seq >= 1),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            prompt_version text CHECK (prompt_version IS NULL OR length(prompt_version) <= 40),
            model_calls integer NOT NULL DEFAULT 0 CHECK (model_calls >= 0),
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz,
            UNIQUE (document_id, posting_id)
        )
        """
    )
    op.execute("CREATE INDEX resume_tailorings_owner_idx ON resume_tailorings (owner_user_id)")
    _rls("resume_tailorings")

    op.execute(
        """
        CREATE TABLE tailoring_suggestions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            tailoring_id uuid NOT NULL REFERENCES resume_tailorings (id) ON DELETE CASCADE,
            unit_id text NOT NULL CHECK (length(unit_id) <= 100),
            target_id text NOT NULL CHECK (length(target_id) <= 60),
            kind text NOT NULL CHECK (kind IN ('bullets', 'paragraph')),
            label text NOT NULL DEFAULT '' CHECK (length(label) <= 120),
            before_lines jsonb NOT NULL,
            after_lines jsonb NOT NULL,
            reason text NOT NULL DEFAULT '' CHECK (length(reason) <= 400),
            requirement_ids jsonb NOT NULL DEFAULT '[]',
            citations jsonb NOT NULL DEFAULT '[]',
            claims jsonb NOT NULL DEFAULT '[]',
            blocked boolean NOT NULL DEFAULT false,
            edited boolean NOT NULL DEFAULT false,
            status text NOT NULL DEFAULT 'pending' CHECK (status IN (
                'pending', 'accepted', 'rejected'
            )),
            ordinal integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            decided_at timestamptz,
            CHECK (pg_column_size(before_lines) <= 20000),
            CHECK (pg_column_size(after_lines) <= 20000)
        )
        """
    )
    op.execute(
        "CREATE INDEX tailoring_suggestions_tailoring_idx "
        "ON tailoring_suggestions (tailoring_id, ordinal)"
    )
    _rls("tailoring_suggestions")


def downgrade() -> None:
    op.execute("DROP TABLE tailoring_suggestions")
    op.execute("DROP TABLE resume_tailorings")
