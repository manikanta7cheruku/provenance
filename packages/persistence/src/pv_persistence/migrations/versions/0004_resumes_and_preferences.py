"""resumes, profile entry provenance, profile preferences

Revision ID: 0004
Revises: 0003

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

All three changes are tenant data and use the same Row Level Security policy as profile_entries:
rows are visible only when app.user_id equals the owner, and no setting yields no rows.

  resumes               one stored resume per user (metadata only; the file is in private storage)
  profile_entries       gains source ("resume" or "user"), the resume it came from, the identity
                        key it was parsed under (so a re-parse recognises it after edits),
                        and an order
  profile_preferences   one row per user, typed so the eligibility engine (1.8) can read it
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE resumes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            original_filename text NOT NULL CHECK (length(original_filename) BETWEEN 1 AND 200),
            file_kind text NOT NULL CHECK (file_kind IN ('pdf', 'docx')),
            size_bytes integer NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 5242880),
            sha256 text NOT NULL CHECK (length(sha256) = 64),
            storage_key text NOT NULL UNIQUE CHECK (storage_key ~ '^resumes/[0-9a-f]{32}$'),
            parse_status text NOT NULL DEFAULT 'uploaded' CHECK (parse_status IN (
                'uploaded', 'parsing', 'parsed', 'parse_failed'
            )),
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN (
                'pending', 'confirmed'
            )),
            parse_generation integer NOT NULL DEFAULT 1 CHECK (parse_generation >= 1),
            page_count integer,
            char_count integer,
            kept_entry_count integer NOT NULL DEFAULT 0,
            dropped_entry_count integer NOT NULL DEFAULT 0,
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            parser_version text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            parsed_at timestamptz,
            confirmed_at timestamptz
        )
        """
    )
    # One resume per user. To change it, delete it and upload another (profile entries stay).
    op.execute("CREATE UNIQUE INDEX resumes_one_per_user ON resumes (owner_user_id)")
    op.execute("ALTER TABLE resumes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE resumes FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON resumes
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )

    op.execute(
        """
        ALTER TABLE profile_entries
            ADD COLUMN source text NOT NULL DEFAULT 'user' CHECK (source IN ('resume', 'user')),
            ADD COLUMN source_resume_id uuid REFERENCES resumes (id) ON DELETE SET NULL,
            ADD COLUMN source_key text,
            ADD COLUMN position integer NOT NULL DEFAULT 0
        """
    )

    op.execute(
        """
        CREATE TABLE profile_preferences (
            owner_user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
            target_roles text[] NOT NULL DEFAULT '{}',
            authorized_countries text[] NOT NULL DEFAULT '{}',
            needs_sponsorship boolean,
            locations text[] NOT NULL DEFAULT '{}',
            open_to_relocate boolean,
            remote_preference text CHECK (remote_preference IS NULL OR remote_preference IN (
                'remote', 'hybrid', 'onsite', 'any'
            )),
            employment_types text[] NOT NULL DEFAULT '{}',
            min_salary_amount integer CHECK (min_salary_amount IS NULL OR min_salary_amount >= 0),
            min_salary_currency text CHECK (min_salary_currency IS NULL OR min_salary_currency IN (
                'INR', 'USD', 'CAD', 'GBP', 'EUR', 'AED', 'SGD', 'AUD'
            )),
            exclusions text[] NOT NULL DEFAULT '{}',
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK ((min_salary_amount IS NULL) = (min_salary_currency IS NULL))
        )
        """
    )
    op.execute("ALTER TABLE profile_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE profile_preferences FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON profile_preferences
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE profile_preferences")
    op.execute(
        "ALTER TABLE profile_entries DROP COLUMN position, DROP COLUMN source_key, "
        "DROP COLUMN source_resume_id, DROP COLUMN source"
    )
    op.execute("DROP TABLE resumes")
