"""duplicate detection: links between fetched jobs, a person's decisions, and sightings

Revision ID: 0012
Revises: 0011

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  source_jobs          gains the normalised company and title (for finding candidates), `group_id`
                       (the smallest id in the connected set of active links) and `seen_count`
                       (how many polls saw the job, the sightings that are kept).
  source_job_links     an edge between two fetched jobs believed to be the same job. Shared
                       reference data, so no Row Level Security. `state` is auto or suggested (made
                       by code), confirmed (accepted by an administrator) or undone (rejected by an
                       administrator). Auto and confirmed links join jobs into a group, so undoing
                       one can split a group again. An undone link is never made again by code.
  posting_links        a person's decision about a public job and a posting they pasted:
                       confirmed ("same job") or undone ("not the same job"). It is tenant data
                       with Row Level Security, so a private posting and the choices about it are
                       visible to its owner only. Public jobs never learn that a private posting
                       exists.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
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
    op.execute("ALTER TABLE source_jobs ADD COLUMN company_norm text")
    op.execute("ALTER TABLE source_jobs ADD COLUMN title_norm text")
    op.execute("ALTER TABLE source_jobs ADD COLUMN group_id uuid")
    op.execute("ALTER TABLE source_jobs ADD COLUMN seen_count integer NOT NULL DEFAULT 1")
    op.execute(
        "ALTER TABLE source_jobs ADD CONSTRAINT source_jobs_seen_count_ck CHECK (seen_count >= 1)"
    )
    op.execute("CREATE INDEX source_jobs_company_idx ON source_jobs (company_norm)")
    op.execute("CREATE INDEX source_jobs_group_idx ON source_jobs (group_id)")
    op.execute("UPDATE source_jobs SET group_id = id WHERE group_id IS NULL")

    op.execute(
        """
        CREATE TABLE source_job_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            job_a uuid NOT NULL REFERENCES source_jobs (id) ON DELETE CASCADE,
            job_b uuid NOT NULL REFERENCES source_jobs (id) ON DELETE CASCADE,
            method text NOT NULL CHECK (length(method) <= 40),
            score numeric(4, 3) NOT NULL CHECK (score >= 0 AND score <= 1),
            reason text NOT NULL DEFAULT '' CHECK (length(reason) <= 300),
            state text NOT NULL CHECK (state IN ('auto', 'suggested', 'confirmed', 'undone')),
            created_at timestamptz NOT NULL DEFAULT now(),
            decided_at timestamptz,
            decided_by uuid REFERENCES users (id) ON DELETE SET NULL,
            CHECK (job_a < job_b),
            UNIQUE (job_a, job_b)
        )
        """
    )
    op.execute("CREATE INDEX source_job_links_b_idx ON source_job_links (job_b)")
    op.execute("CREATE INDEX source_job_links_state_idx ON source_job_links (state)")

    op.execute(
        """
        CREATE TABLE posting_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            source_job_id uuid NOT NULL REFERENCES source_jobs (id) ON DELETE CASCADE,
            state text NOT NULL CHECK (state IN ('confirmed', 'undone')),
            created_at timestamptz NOT NULL DEFAULT now(),
            decided_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (posting_id, source_job_id)
        )
        """
    )
    op.execute("CREATE INDEX posting_links_owner_idx ON posting_links (owner_user_id, posting_id)")
    _rls("posting_links")


def downgrade() -> None:
    op.execute("DROP TABLE posting_links")
    op.execute("DROP TABLE source_job_links")
    op.execute("ALTER TABLE source_jobs DROP CONSTRAINT source_jobs_seen_count_ck")
    op.execute("ALTER TABLE source_jobs DROP COLUMN seen_count")
    op.execute("ALTER TABLE source_jobs DROP COLUMN group_id")
    op.execute("ALTER TABLE source_jobs DROP COLUMN title_norm")
    op.execute("ALTER TABLE source_jobs DROP COLUMN company_norm")
