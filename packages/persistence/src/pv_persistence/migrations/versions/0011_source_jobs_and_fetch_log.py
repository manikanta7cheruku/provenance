"""jobs fetched from sources, what was asked of each board, and a log of every fetch

Revision ID: 0011
Revises: 0010

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

These tables hold shared reference data (public job postings and the record of asking for them), not
tenant data, so there is no Row Level Security. Who may see a job is decided on read: a job is shown
only while its source is enabled, verified and in date.

  source_jobs     one job as a source published it, reduced to plain text and an https address.
                  Unique per source, board and the source's own id. `closed_at` is set when a
                  complete listing no longer contains the job.
  source_targets  one row per board asked for: when it was last asked, and how it went. The minimum
                  poll interval is enforced from this.
  fetch_log       one row per fetch attempt or skip, with the outcome and counts, never any job text.
  job_sources     gains breaker_open_until: the time until which the source is left alone.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE job_sources ADD COLUMN breaker_open_until timestamptz")
    op.execute(
        """
        CREATE TABLE source_jobs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_key text NOT NULL REFERENCES job_sources (key) ON DELETE CASCADE,
            board_id text NOT NULL CHECK (length(board_id) BETWEEN 1 AND 100),
            external_id text NOT NULL CHECK (length(external_id) BETWEEN 1 AND 100),
            url text NOT NULL CHECK (url LIKE 'https://%' AND length(url) <= 500),
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            company_name text CHECK (company_name IS NULL OR length(company_name) <= 120),
            location text NOT NULL DEFAULT '' CHECK (length(location) <= 200),
            workplace text CHECK (workplace IS NULL OR workplace IN ('remote', 'hybrid', 'onsite')),
            employment_type text CHECK (employment_type IS NULL OR employment_type IN (
                'full_time', 'part_time', 'internship', 'contract', 'freelance'
            )),
            department text NOT NULL DEFAULT '' CHECK (length(department) <= 200),
            description text NOT NULL DEFAULT '' CHECK (length(description) <= 20000),
            posted_at timestamptz,
            source_updated_at timestamptz,
            content_hash text NOT NULL CHECK (length(content_hash) = 64),
            first_seen_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            closed_at timestamptz,
            UNIQUE (source_key, board_id, external_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX source_jobs_open_idx ON source_jobs (source_key, board_id) "
        "WHERE closed_at IS NULL"
    )
    op.execute("CREATE INDEX source_jobs_seen_idx ON source_jobs (last_seen_at DESC)")
    op.execute(
        """
        CREATE TABLE source_targets (
            source_key text NOT NULL REFERENCES job_sources (key) ON DELETE CASCADE,
            board_id text NOT NULL CHECK (length(board_id) BETWEEN 1 AND 100),
            last_polled_at timestamptz,
            last_outcome text CHECK (last_outcome IS NULL OR length(last_outcome) <= 40),
            consecutive_errors integer NOT NULL DEFAULT 0 CHECK (consecutive_errors >= 0),
            jobs_open integer NOT NULL DEFAULT 0 CHECK (jobs_open >= 0),
            PRIMARY KEY (source_key, board_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE fetch_log (
            id bigserial PRIMARY KEY,
            source_key text NOT NULL REFERENCES job_sources (key) ON DELETE CASCADE,
            board_id text CHECK (board_id IS NULL OR length(board_id) <= 100),
            started_at timestamptz NOT NULL DEFAULT now(),
            duration_ms integer NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
            outcome text NOT NULL CHECK (outcome IN (
                'ok', 'rate_limited', 'http_error', 'network_error', 'bad_response',
                'not_found', 'skipped_breaker', 'skipped_interval', 'skipped_unusable'
            )),
            http_status integer,
            bytes_read integer NOT NULL DEFAULT 0 CHECK (bytes_read >= 0),
            jobs_seen integer NOT NULL DEFAULT 0 CHECK (jobs_seen >= 0),
            jobs_new integer NOT NULL DEFAULT 0 CHECK (jobs_new >= 0),
            jobs_changed integer NOT NULL DEFAULT 0 CHECK (jobs_changed >= 0),
            jobs_closed integer NOT NULL DEFAULT 0 CHECK (jobs_closed >= 0),
            jobs_skipped integer NOT NULL DEFAULT 0 CHECK (jobs_skipped >= 0),
            error_class text CHECK (error_class IS NULL OR length(error_class) <= 60)
        )
        """
    )
    op.execute("CREATE INDEX fetch_log_source_idx ON fetch_log (source_key, started_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE fetch_log")
    op.execute("DROP TABLE source_targets")
    op.execute("DROP TABLE source_jobs")
    op.execute("ALTER TABLE job_sources DROP COLUMN breaker_open_until")
