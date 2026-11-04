"""workbench: a person's decisions about jobs, the log of each move, saved views

Revision ID: 0014
Revises: 0013

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  job_decisions        what a person has decided about one posting: new, saved, dismissed,
                       approved for preparation, applied or archived, with a private note and the
                       date they applied. A posting with no row is new. One row per posting.
  job_decision_events  every move, with the action and the states either side. It is what lets
                       "Undo applied" return a job to where it was, and it is the audit trail of the
                       person's own decisions. It holds no note text.
  workbench_views      a saved view: a name and the filters and sort, as validated JSON.
  job_postings         `acquisition_method` accepts source_job: a posting made from a job found on
                       a permitted source ("Add to my jobs").

All three new tables are tenant data with Row Level Security enabled and forced. They cascade with
the posting and with the person.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
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
                'user_paste', 'manual_entry', 'csv_import', 'xlsx_import', 'url_import',
                'source_job'
            ))
        """
    )

    op.execute(
        """
        CREATE TABLE job_decisions (
            posting_id uuid PRIMARY KEY REFERENCES job_postings (id) ON DELETE CASCADE,
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            state text NOT NULL DEFAULT 'new' CHECK (state IN (
                'new', 'saved', 'dismissed', 'approved_for_prep', 'applied', 'archived'
            )),
            note text NOT NULL DEFAULT '' CHECK (length(note) <= 2000),
            applied_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (state <> 'applied' OR applied_at IS NOT NULL)
        )
        """
    )
    op.execute("CREATE INDEX job_decisions_owner_state_idx ON job_decisions (owner_user_id, state)")
    _rls("job_decisions")

    op.execute(
        """
        CREATE TABLE job_decision_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            action text NOT NULL CHECK (action IN (
                'save', 'unsave', 'dismiss', 'undo_dismiss', 'approve', 'mark_applied',
                'undo_applied', 'archive'
            )),
            from_state text NOT NULL,
            to_state text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX job_decision_events_posting_idx "
        "ON job_decision_events (posting_id, created_at DESC)"
    )
    _rls("job_decision_events")

    op.execute(
        """
        CREATE TABLE workbench_views (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
            query jsonb NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX workbench_views_owner_name_uniq "
        "ON workbench_views (owner_user_id, lower(name))"
    )
    _rls("workbench_views")


def downgrade() -> None:
    op.execute("DROP TABLE workbench_views")
    op.execute("DROP TABLE job_decision_events")
    op.execute("DROP TABLE job_decisions")
    op.execute("DELETE FROM job_postings WHERE acquisition_method = 'source_job'")
    op.execute("ALTER TABLE job_postings DROP CONSTRAINT job_postings_acquisition_method_check")
    op.execute(
        """
        ALTER TABLE job_postings ADD CONSTRAINT job_postings_acquisition_method_check
            CHECK (acquisition_method IN (
                'user_paste', 'manual_entry', 'csv_import', 'xlsx_import', 'url_import'
            ))
        """
    )
