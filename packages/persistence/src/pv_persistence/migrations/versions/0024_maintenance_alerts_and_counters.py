"""maintenance, alert delivery, plan on model calls, feedback counters

Revision ID: 0024
Revises: 0023

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  alert_deliveries   which alerts have been emailed to administrators and when, so an alert is sent
                     once, again only after a cooldown, and the record is cleared when it resolves.
                     A system table with no person in it.
  llm_calls.plan_id  the plan of the person when a model call was made, so cost can be added up by
                     plan without reading any tenant table (C-143). NULL means the default plan.
  feedback_totals,   how many "was this right?" labels exist and how many people gave them, kept by
  feedback_people    triggers, so administrators can see whether there are enough labels to compare
                     a learned ranker (ADR-0054) without reading anyone's labels. The counters hold
                     no content. The triggers are SECURITY DEFINER with a fixed search path so the
                     application role can read the counters and cannot change them.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE alert_deliveries (
            alert_key text PRIMARY KEY CHECK (length(alert_key) BETWEEN 1 AND 120),
            severity text NOT NULL CHECK (severity IN ('critical', 'warning')),
            first_sent_at timestamptz NOT NULL DEFAULT now(),
            last_sent_at timestamptz NOT NULL DEFAULT now(),
            times_sent integer NOT NULL DEFAULT 1 CHECK (times_sent >= 1)
        )
        """
    )
    op.execute(
        "ALTER TABLE llm_calls ADD COLUMN plan_id text CHECK (plan_id IS NULL OR length(plan_id) <= 60)"
    )

    op.execute(
        """
        CREATE TABLE feedback_totals (
            id integer PRIMARY KEY CHECK (id = 1),
            labels bigint NOT NULL DEFAULT 0 CHECK (labels >= 0)
        )
        """
    )
    op.execute("INSERT INTO feedback_totals (id, labels) VALUES (1, 0)")
    op.execute(
        """
        CREATE TABLE feedback_people (
            user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION count_feedback_label() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE feedback_totals SET labels = labels + 1 WHERE id = 1;
                INSERT INTO feedback_people (user_id) VALUES (NEW.owner_user_id) ON CONFLICT DO NOTHING;
                RETURN NEW;
            END IF;
            UPDATE feedback_totals SET labels = greatest(labels - 1, 0) WHERE id = 1;
            RETURN OLD;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER verdict_feedback_count_insert AFTER INSERT ON verdict_feedback "
        "FOR EACH ROW EXECUTE FUNCTION count_feedback_label()"
    )
    op.execute(
        "CREATE TRIGGER verdict_feedback_count_delete AFTER DELETE ON verdict_feedback "
        "FOR EACH ROW EXECUTE FUNCTION count_feedback_label()"
    )
    # Count what already exists. Run as the owner, which sees every row only if it bypasses Row Level
    # Security (it does in development). Where it does not, the counters start at zero and only count
    # new labels, which is the safe direction for a "do we have enough" question.
    op.execute(
        "UPDATE feedback_totals SET labels = (SELECT count(*) FROM verdict_feedback) WHERE id = 1"
    )
    op.execute(
        "INSERT INTO feedback_people (user_id) SELECT DISTINCT owner_user_id FROM verdict_feedback "
        "ON CONFLICT DO NOTHING"
    )
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON feedback_totals, feedback_people FROM provenance_app"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER verdict_feedback_count_delete ON verdict_feedback")
    op.execute("DROP TRIGGER verdict_feedback_count_insert ON verdict_feedback")
    op.execute("DROP FUNCTION count_feedback_label()")
    op.execute("DROP TABLE feedback_people")
    op.execute("DROP TABLE feedback_totals")
    op.execute("ALTER TABLE llm_calls DROP COLUMN plan_id")
    op.execute("DROP TABLE alert_deliveries")
