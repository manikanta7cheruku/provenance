"""source registry and company registry

Revision ID: 0010
Revises: 0009

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

These two tables are shared reference data, not tenant data, so they have no Row Level Security:
every signed-in person reads the same registry, and only an administrator changes it (checked in
the API, each change audited).

  job_sources  where jobs can come from, what each source can do, and the record of where its terms
               were read. A source cannot be enabled unless it is verified, reviewed within the
               window, and has a reviewer (a CHECK here and the same rule in code).
               `edited_at` is set when an administrator changes a row, so a later seed never
               overwrites it.
  companies    the company registry used to resolve names without a model.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE job_sources (
            key text PRIMARY KEY CHECK (key ~ '^[A-Za-z0-9_-]{1,40}$'),
            display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 80),
            source_type text NOT NULL CHECK (source_type IN (
                'ats_board', 'job_api', 'public_feed', 'company_careers', 'user_import_only'
            )),
            adapter text CHECK (adapter IS NULL OR length(adapter) <= 60),
            endpoint_or_feed text CHECK (endpoint_or_feed IS NULL OR length(endpoint_or_feed) <= 500),
            capabilities jsonb NOT NULL DEFAULT '{}',
            auth_requirements text NOT NULL DEFAULT 'None' CHECK (length(auth_requirements) <= 2000),
            compliance_status text NOT NULL DEFAULT 'unverified' CHECK (compliance_status IN (
                'verified', 'unverified', 'restricted', 'prohibited'
            )),
            terms_checked_at date,
            terms_url text CHECK (terms_url IS NULL OR length(terms_url) <= 500),
            verification_owner text CHECK (verification_owner IS NULL OR length(verification_owner) <= 500),
            rate_limit text NOT NULL DEFAULT '' CHECK (length(rate_limit) <= 2000),
            quota_policy text NOT NULL DEFAULT '' CHECK (length(quota_policy) <= 2000),
            min_poll_interval_seconds integer NOT NULL DEFAULT 3600 CHECK (min_poll_interval_seconds >= 0),
            attribution_text text NOT NULL DEFAULT '' CHECK (length(attribution_text) <= 2000),
            geographic_coverage jsonb NOT NULL DEFAULT '[]',
            supports_user_import boolean NOT NULL DEFAULT true,
            enabled boolean NOT NULL DEFAULT false,
            compliance_notes text NOT NULL DEFAULT '' CHECK (length(compliance_notes) <= 4000),
            health_status text NOT NULL DEFAULT 'unknown' CHECK (health_status IN (
                'unknown', 'healthy', 'degraded', 'down'
            )),
            last_success_at timestamptz,
            last_failure_at timestamptz,
            failure_streak integer NOT NULL DEFAULT 0 CHECK (failure_streak >= 0),
            edited_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (
                NOT enabled OR (
                    compliance_status = 'verified'
                    AND terms_checked_at IS NOT NULL
                    AND terms_url IS NOT NULL
                    AND verification_owner IS NOT NULL
                    AND source_type <> 'user_import_only'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE companies (
            key text PRIMARY KEY CHECK (key ~ '^[A-Za-z0-9_-]{1,60}$'),
            canonical_name text NOT NULL CHECK (length(canonical_name) BETWEEN 1 AND 120),
            aliases jsonb NOT NULL DEFAULT '[]',
            domain text CHECK (domain IS NULL OR length(domain) <= 200),
            career_url text CHECK (career_url IS NULL OR length(career_url) <= 500),
            ats_platform text CHECK (ats_platform IS NULL OR length(ats_platform) <= 40),
            ats_board_id text CHECK (ats_board_id IS NULL OR length(ats_board_id) <= 100),
            industry text CHECK (industry IS NULL OR length(industry) <= 80),
            country text CHECK (country IS NULL OR length(country) <= 80),
            last_verified_at date,
            edited_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE companies")
    op.execute("DROP TABLE job_sources")
