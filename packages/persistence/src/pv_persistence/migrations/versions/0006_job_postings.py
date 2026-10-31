"""job postings and their requirements

Revision ID: 0006
Revises: 0005

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

Both tables are tenant data and use the same Row Level Security policy as profile_entries.

  job_postings      one row per posting a person pasted. The raw text is kept (capped), so
                    every quote can be checked against it. source_name is the label the person
                    chose and acquisition_method is how the text reached us, stored apart so we
                    never say we "searched" a site the person copied from. (owner, content_hash)
                    is unique: pasting the same posting again finds the first one instead of
                    paying for another read.
  job_requirements  what the posting asks for, each with the posting's own words and where they are.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE job_postings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            visibility text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private')),
            source_name text NOT NULL CHECK (length(source_name) BETWEEN 1 AND 80),
            acquisition_method text NOT NULL DEFAULT 'user_paste'
                CHECK (acquisition_method IN ('user_paste')),
            source_url text CHECK (source_url IS NULL OR (length(source_url) <= 500
                AND source_url ~* '^https?://')),
            raw_text text NOT NULL CHECK (length(raw_text) BETWEEN 100 AND 20000),
            content_hash text NOT NULL CHECK (length(content_hash) = 64),
            title text CHECK (title IS NULL OR length(title) <= 200),
            company text CHECK (company IS NULL OR length(company) <= 200),
            facts jsonb NOT NULL DEFAULT '{}',
            parse_status text NOT NULL DEFAULT 'queued' CHECK (parse_status IN (
                'queued', 'extracting', 'extracted', 'failed'
            )),
            analysis_generation integer NOT NULL DEFAULT 1 CHECK (analysis_generation >= 1),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            facts_dropped integer NOT NULL DEFAULT 0,
            requirements_dropped integer NOT NULL DEFAULT 0,
            prompt_version text,
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            extracted_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX job_postings_owner_hash_uniq "
        "ON job_postings (owner_user_id, content_hash)"
    )
    op.execute(
        "CREATE INDEX job_postings_owner_created_idx "
        "ON job_postings (owner_user_id, created_at DESC)"
    )
    op.execute("ALTER TABLE job_postings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job_postings FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON job_postings
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE job_requirements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            ordinal integer NOT NULL CHECK (ordinal >= 0),
            text text NOT NULL CHECK (length(text) BETWEEN 1 AND 400),
            kind text NOT NULL CHECK (kind IN ('required', 'preferred')),
            category text NOT NULL CHECK (category IN (
                'skill', 'experience', 'education', 'certification',
                'language', 'work_authorization', 'location', 'other'
            )),
            years_min integer CHECK (years_min IS NULL OR years_min BETWEEN 0 AND 60),
            quote text NOT NULL CHECK (length(quote) BETWEEN 1 AND 400),
            quote_start integer NOT NULL CHECK (quote_start >= 0),
            quote_end integer NOT NULL CHECK (quote_end > quote_start),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (posting_id, ordinal)
        )
        """
    )
    op.execute("ALTER TABLE job_requirements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job_requirements FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON job_requirements
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE job_requirements")
    op.execute("DROP TABLE job_postings")
