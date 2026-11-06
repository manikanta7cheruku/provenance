"""evaluation runs

Revision ID: 0022
Revises: 0021

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  evaluation_runs  one row per evaluation run: which suite, the dataset and the versions of our
                   rules and prompts it ran with, the git commit, every metric against its limit
                   and baseline, and the cases that failed. The dataset is synthetic, so a run
                   holds no personal data.

This is a system table, like the task queue and the model call log: it has no Row Level Security
because no row belongs to a person. The application role may add and read rows but not change or
remove them, so a stored result is a record.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evaluation_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at timestamptz NOT NULL DEFAULT now(),
            suite text NOT NULL CHECK (suite IN ('deterministic', 'llm')),
            trigger text NOT NULL DEFAULT 'manual' CHECK (trigger IN ('manual', 'ci', 'scheduled')),
            dataset_version text NOT NULL,
            git_sha text CHECK (git_sha IS NULL OR length(git_sha) <= 64),
            model text CHECK (model IS NULL OR length(model) <= 120),
            passed boolean NOT NULL,
            case_count integer NOT NULL CHECK (case_count >= 0),
            failure_count integer NOT NULL CHECK (failure_count >= 0),
            versions jsonb NOT NULL DEFAULT '{}'::jsonb,
            metrics jsonb NOT NULL DEFAULT '[]'::jsonb,
            suites jsonb NOT NULL DEFAULT '{}'::jsonb,
            failures jsonb NOT NULL DEFAULT '[]'::jsonb
        )
        """
    )
    op.execute(
        "CREATE INDEX evaluation_runs_suite_created_idx ON evaluation_runs (suite, created_at DESC)"
    )
    op.execute("REVOKE UPDATE, DELETE ON evaluation_runs FROM provenance_app")


def downgrade() -> None:
    op.execute("DROP TABLE evaluation_runs")
