"""plans, entitlements and the usage ledger

Revision ID: 0020
Revises: 0019

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  plans         the plans and their limits, as data. Not tenant data: every person may read the list.
                The application role can read it and cannot change it (the privileges are revoked
                below), so a limit can only be changed by the database owner, never by a request.
                The three rows are provisional starting points (see pv_domain.entitlements): the
                business model sets real numbers from measured cost.
  user_plans    which plan a person is on. No row means the default plan. Tenant data with Row Level
                Security, so a person can read their own row. It is written by the operator command
                `set-plan`, which acts for one person at a time.
  usage_ledger  one row per billable event: what, how many, which month, and a key. The same key in
                the same month is the same event, so a retried request is never charged twice. Tenant
                data with Row Level Security enabled and forced, and goes with the person.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE plans (
            id text PRIMARY KEY CHECK (id ~ '^[a-z][a-z0-9_]{1,30}$'),
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 40),
            sort_order integer NOT NULL DEFAULT 0,
            data jsonb NOT NULL DEFAULT '{}'::jsonb,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("REVOKE INSERT, UPDATE, DELETE ON plans FROM provenance_app")
    # exec_driver_sql, because text() would read the colons inside the JSON as parameters.
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO plans (id, label, sort_order, data)
        VALUES ('free', 'Free', 1, '{"units":{"discovery_run":20,"job_analysis":30,"url_analysis":15,"material_generation":20},"resumes":1,"exports_per_resume":5}'::jsonb)
        """
    )
    # exec_driver_sql, because text() would read the colons inside the JSON as parameters.
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO plans (id, label, sort_order, data)
        VALUES ('starter', 'Starter', 2, '{"units":{"discovery_run":100,"job_analysis":150,"url_analysis":75,"material_generation":100},"resumes":3,"exports_per_resume":20}'::jsonb)
        """
    )
    # exec_driver_sql, because text() would read the colons inside the JSON as parameters.
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO plans (id, label, sort_order, data)
        VALUES ('pro', 'Pro', 3, '{"units":{"discovery_run":500,"job_analysis":800,"url_analysis":300,"material_generation":500},"resumes":10,"exports_per_resume":50}'::jsonb)
        """
    )
    op.execute(
        """
        CREATE TABLE user_plans (
            owner_user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
            plan_id text NOT NULL REFERENCES plans (id),
            assigned_by text NOT NULL DEFAULT 'operator' CHECK (length(assigned_by) <= 60),
            assigned_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE usage_ledger (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            unit text NOT NULL CHECK (unit IN
                ('discovery_run', 'job_analysis', 'url_analysis', 'material_generation')),
            amount integer NOT NULL DEFAULT 1 CHECK (amount BETWEEN 1 AND 1000),
            period_start date NOT NULL,
            event_key text NOT NULL CHECK (length(event_key) BETWEEN 1 AND 160),
            plan_id text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (owner_user_id, unit, period_start, event_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX usage_ledger_owner_period_idx "
        "ON usage_ledger (owner_user_id, period_start, unit)"
    )
    op.execute("ALTER TABLE user_plans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_plans FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON user_plans
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )
    op.execute("ALTER TABLE usage_ledger ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE usage_ledger FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON usage_ledger
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE usage_ledger")
    op.execute("DROP TABLE user_plans")
    op.execute("DROP TABLE plans")
