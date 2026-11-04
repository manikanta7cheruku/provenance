"""shortlist email and application drafts

Revision ID: 0015
Revises: 0014

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  application_drafts   a cover note or an answer to a question, written for one posting from the
                       person's own evidence. `evidence` keeps the passages the draft may use, so the
                       claim check can run again when the person edits. `claims` is the result of the
                       last check. The text is the person's: editing marks it as edited. One draft
                       per posting, kind and question. `seq` lets a new request make an older task do
                       nothing.
  shortlist_settings   a person's shortlist schedule: off by default, daily or weekly, an hour, their
                       time zone and how many jobs. `next_run_at` is when the next email is due.
  shortlist_runs       one row per due time: sent, nothing to send, skipped (address not verified) or
                       failed. Unique per person and time, so a retried task cannot send twice.
  shortlist_items      the jobs in each email, so a job is never sent twice.

All four tables are tenant data with Row Level Security enabled and forced and go with the person and
the posting.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
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
        CREATE TABLE application_drafts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            kind text NOT NULL CHECK (kind IN ('cover_note', 'answer')),
            question text NOT NULL DEFAULT '' CHECK (length(question) <= 300),
            question_key text NOT NULL DEFAULT '' CHECK (length(question_key) <= 120),
            body text NOT NULL DEFAULT '' CHECK (length(body) <= 6000),
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'working', 'ready', 'failed')),
            origin text NOT NULL DEFAULT 'model' CHECK (origin IN ('model', 'edited')),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            seq integer NOT NULL DEFAULT 1 CHECK (seq >= 1),
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            prompt_version text,
            model_calls integer NOT NULL DEFAULT 0 CHECK (model_calls >= 0),
            evidence jsonb NOT NULL DEFAULT '[]',
            claims jsonb NOT NULL DEFAULT '[]',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (kind = 'answer' OR question = ''),
            CHECK (kind = 'cover_note' OR length(question) >= 1)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX application_drafts_one_uniq "
        "ON application_drafts (owner_user_id, posting_id, kind, question_key)"
    )
    op.execute("CREATE INDEX application_drafts_posting_idx ON application_drafts (posting_id)")
    _rls("application_drafts")

    op.execute(
        """
        CREATE TABLE shortlist_settings (
            owner_user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
            enabled boolean NOT NULL DEFAULT false,
            frequency text NOT NULL DEFAULT 'weekly' CHECK (frequency IN ('daily', 'weekly')),
            weekday smallint NOT NULL DEFAULT 0 CHECK (weekday BETWEEN 0 AND 6),
            hour smallint NOT NULL DEFAULT 8 CHECK (hour BETWEEN 0 AND 23),
            timezone text NOT NULL DEFAULT 'UTC' CHECK (length(timezone) BETWEEN 1 AND 64),
            max_items smallint NOT NULL DEFAULT 5 CHECK (max_items BETWEEN 1 AND 10),
            next_run_at timestamptz,
            last_run_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (NOT enabled OR next_run_at IS NOT NULL)
        )
        """
    )
    _rls("shortlist_settings")

    op.execute(
        """
        CREATE TABLE shortlist_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            slot timestamptz NOT NULL,
            manual boolean NOT NULL DEFAULT false,
            outcome text NOT NULL CHECK (outcome IN ('sent', 'nothing', 'skipped', 'failed')),
            item_count integer NOT NULL DEFAULT 0 CHECK (item_count >= 0),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (owner_user_id, slot)
        )
        """
    )
    op.execute(
        "CREATE INDEX shortlist_runs_owner_idx ON shortlist_runs (owner_user_id, created_at DESC)"
    )
    _rls("shortlist_runs")

    op.execute(
        """
        CREATE TABLE shortlist_items (
            run_id uuid NOT NULL REFERENCES shortlist_runs (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            position smallint NOT NULL CHECK (position >= 1),
            PRIMARY KEY (run_id, posting_id)
        )
        """
    )
    op.execute("CREATE INDEX shortlist_items_posting_idx ON shortlist_items (posting_id)")
    _rls("shortlist_items")


def downgrade() -> None:
    op.execute("DROP TABLE shortlist_items")
    op.execute("DROP TABLE shortlist_runs")
    op.execute("DROP TABLE shortlist_settings")
    op.execute("DROP TABLE application_drafts")
