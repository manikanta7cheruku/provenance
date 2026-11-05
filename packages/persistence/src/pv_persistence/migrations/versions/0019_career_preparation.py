"""career preparation

Revision ID: 0019
Revises: 0018

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  job_preparations  one row per person and job: the interview date, the person's own notes and link
                    about the company. Nothing generated lives here.
  prep_outputs      one row per person, job and kind of preparation (interview questions, an
                    outreach message and so on): the status of the work, the items or text it
                    produced, the evidence it was given and every claim in it checked against
                    that evidence.
  prep_progress     what the person has ticked as done, by a stable key.
  mock_interviews   a practice session: the questions and, answer by answer, the person's words and
                    the rubric feedback computed from them.

All are tenant data with Row Level Security enabled and forced, and go with the person and the job.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE job_preparations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            interview_date date,
            company_link text NOT NULL DEFAULT '' CHECK (length(company_link) <= 500),
            company_notes text NOT NULL DEFAULT '' CHECK (length(company_notes) <= 4000),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (owner_user_id, posting_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE prep_outputs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            action text NOT NULL CHECK (length(action) BETWEEN 1 AND 40),
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'working', 'ready', 'failed')),
            origin text NOT NULL DEFAULT 'model' CHECK (origin IN ('model', 'edited')),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            seq integer NOT NULL DEFAULT 1,
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            prompt_version text,
            model_calls integer NOT NULL DEFAULT 0,
            items jsonb NOT NULL DEFAULT '[]'::jsonb,
            body text NOT NULL DEFAULT '' CHECK (length(body) <= 6000),
            evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
            claims jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (owner_user_id, posting_id, action)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE prep_progress (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            item_key text NOT NULL CHECK (length(item_key) BETWEEN 1 AND 120),
            done boolean NOT NULL DEFAULT true,
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (owner_user_id, posting_id, item_key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE mock_interviews (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            state text NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'finished')),
            questions jsonb NOT NULL DEFAULT '[]'::jsonb,
            turns jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX mock_interviews_owner_posting_idx "
        "ON mock_interviews (owner_user_id, posting_id, created_at DESC)"
    )
    op.execute("ALTER TABLE job_preparations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job_preparations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON job_preparations
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )
    op.execute("ALTER TABLE prep_outputs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE prep_outputs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON prep_outputs
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )
    op.execute("ALTER TABLE prep_progress ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE prep_progress FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON prep_progress
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )
    op.execute("ALTER TABLE mock_interviews ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mock_interviews FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON mock_interviews
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE mock_interviews")
    op.execute("DROP TABLE prep_progress")
    op.execute("DROP TABLE prep_outputs")
    op.execute("DROP TABLE job_preparations")
