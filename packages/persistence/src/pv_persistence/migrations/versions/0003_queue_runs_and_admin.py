"""task queue, workflow runs and steps, model call ledger, user counters, invite lifecycle

Revision ID: 0003
Revises: 0002

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

Row Level Security split (ADR-0022):
  workflow_runs, workflow_steps   tenant data, RLS enabled and forced, fail closed
  tasks, worker_heartbeats,       system tables, no RLS: the worker claims across tenants and
  llm_calls, user_stats           the admin overview needs cross-tenant counts. They hold
                                  metadata only. No prompt or response text has a column.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- workflow runs and steps (tenant data)
    op.execute(
        """
        CREATE TABLE workflow_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            workflow_type text NOT NULL,
            state text NOT NULL DEFAULT 'queued' CHECK (state IN (
                'queued', 'running', 'needs_user_input', 'retrying',
                'succeeded', 'failed', 'cancelled'
            )),
            can_retry boolean NOT NULL DEFAULT false,
            subject_type text,
            subject_id text,
            error_class text,
            error_summary text CHECK (error_summary IS NULL OR length(error_summary) <= 300),
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            finished_at timestamptz,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX workflow_runs_owner_idx ON workflow_runs (owner_user_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE workflow_steps (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id uuid NOT NULL REFERENCES workflow_runs (id) ON DELETE CASCADE,
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            step_name text NOT NULL,
            ordinal integer NOT NULL,
            state text NOT NULL DEFAULT 'pending' CHECK (state IN (
                'pending', 'running', 'succeeded', 'failed', 'skipped'
            )),
            started_at timestamptz,
            finished_at timestamptz,
            duration_ms integer,
            error_class text,
            error_summary text CHECK (error_summary IS NULL OR length(error_summary) <= 300),
            detail jsonb NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX workflow_steps_run_idx ON workflow_steps (run_id, ordinal)")
    op.execute("ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workflow_runs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON workflow_runs
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )
    op.execute("ALTER TABLE workflow_steps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workflow_steps FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON workflow_steps
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )

    # ---- task queue (system table)
    op.execute(
        """
        CREATE TABLE tasks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            task_type text NOT NULL,
            payload jsonb NOT NULL DEFAULT '{}',
            state text NOT NULL DEFAULT 'queued' CHECK (state IN (
                'queued', 'running', 'succeeded', 'retry_scheduled', 'dead_letter', 'cancelled'
            )),
            owner_user_id uuid REFERENCES users (id) ON DELETE CASCADE,
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            idempotency_key text NOT NULL UNIQUE,
            attempts integer NOT NULL DEFAULT 0,
            max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts >= 1),
            run_after timestamptz NOT NULL DEFAULT now(),
            locked_until timestamptz,
            locked_by text,
            last_error text CHECK (last_error IS NULL OR length(last_error) <= 300),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        )
        """
    )
    # Claim path: waiting tasks ordered by when they become due, and running tasks whose
    # lease may have expired. Partial indexes keep both tiny however many tasks finished.
    op.execute(
        """
        CREATE INDEX tasks_due_idx ON tasks (run_after)
            WHERE state IN ('queued', 'retry_scheduled')
        """
    )
    op.execute("CREATE INDEX tasks_lease_idx ON tasks (locked_until) WHERE state = 'running'")
    op.execute("CREATE INDEX tasks_state_idx ON tasks (state, created_at)")
    op.execute(
        """
        CREATE INDEX tasks_owner_idx ON tasks (owner_user_id)
            WHERE owner_user_id IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE worker_heartbeats (
            worker_id text PRIMARY KEY,
            hostname text NOT NULL,
            started_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            tasks_processed integer NOT NULL DEFAULT 0
        )
        """
    )

    # ---- model call ledger (metadata only, append-only for the application role)
    op.execute(
        """
        CREATE TABLE llm_calls (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            user_id uuid REFERENCES users (id) ON DELETE SET NULL,
            purpose text NOT NULL,
            provider text NOT NULL,
            model text NOT NULL,
            prompt_version text,
            input_tokens integer NOT NULL DEFAULT 0,
            output_tokens integer NOT NULL DEFAULT 0,
            estimated_cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
            latency_ms integer NOT NULL DEFAULT 0,
            status text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'error')),
            error_class text,
            content_hash text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX llm_calls_created_idx ON llm_calls (created_at DESC)")
    op.execute("CREATE INDEX llm_calls_run_idx ON llm_calls (run_id) WHERE run_id IS NOT NULL")
    op.execute("REVOKE UPDATE, DELETE ON llm_calls FROM provenance_app")

    # ---- counters an administrator may see instead of tenant data
    op.execute(
        """
        CREATE TABLE user_stats (
            user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
            profile_entries_count integer NOT NULL DEFAULT 0,
            runs_count integer NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Existing users start at zero. Counters count from this migration onward: the owner role
    # cannot read RLS-protected rows to backfill them (FORCE ROW LEVEL SECURITY).
    op.execute("INSERT INTO user_stats (user_id) SELECT id FROM users")
    op.execute(
        """
        CREATE FUNCTION pv_user_stats_for_new_user() RETURNS trigger
        LANGUAGE plpgsql AS $fn$
        BEGIN
            INSERT INTO user_stats (user_id) VALUES (NEW.id) ON CONFLICT (user_id) DO NOTHING;
            RETURN NEW;
        END
        $fn$
        """
    )
    op.execute(
        """
        CREATE TRIGGER users_create_stats AFTER INSERT ON users
            FOR EACH ROW EXECUTE FUNCTION pv_user_stats_for_new_user()
        """
    )
    op.execute(
        """
        CREATE FUNCTION pv_count_profile_entry() RETURNS trigger
        LANGUAGE plpgsql AS $fn$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE user_stats
                   SET profile_entries_count = profile_entries_count + 1, updated_at = now()
                 WHERE user_id = NEW.owner_user_id;
                RETURN NEW;
            END IF;
            UPDATE user_stats
               SET profile_entries_count = greatest(profile_entries_count - 1, 0),
                   updated_at = now()
             WHERE user_id = OLD.owner_user_id;
            RETURN OLD;
        END
        $fn$
        """
    )
    op.execute(
        """
        CREATE TRIGGER profile_entries_count_stats AFTER INSERT OR DELETE ON profile_entries
            FOR EACH ROW EXECUTE FUNCTION pv_count_profile_entry()
        """
    )
    op.execute(
        """
        CREATE FUNCTION pv_count_run() RETURNS trigger
        LANGUAGE plpgsql AS $fn$
        BEGIN
            UPDATE user_stats SET runs_count = runs_count + 1, updated_at = now()
             WHERE user_id = NEW.owner_user_id;
            RETURN NEW;
        END
        $fn$
        """
    )
    op.execute(
        """
        CREATE TRIGGER workflow_runs_count_stats AFTER INSERT ON workflow_runs
            FOR EACH ROW EXECUTE FUNCTION pv_count_run()
        """
    )

    # ---- invite lifecycle
    op.execute(
        """
        ALTER TABLE invites
            ADD COLUMN created_by uuid REFERENCES users (id) ON DELETE SET NULL
        """
    )
    op.execute("ALTER TABLE invites ADD COLUMN revoked_at timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE invites DROP COLUMN revoked_at")
    op.execute("ALTER TABLE invites DROP COLUMN created_by")
    op.execute("DROP TRIGGER workflow_runs_count_stats ON workflow_runs")
    op.execute("DROP FUNCTION pv_count_run()")
    op.execute("DROP TRIGGER profile_entries_count_stats ON profile_entries")
    op.execute("DROP FUNCTION pv_count_profile_entry()")
    op.execute("DROP TRIGGER users_create_stats ON users")
    op.execute("DROP FUNCTION pv_user_stats_for_new_user()")
    op.execute("DROP TABLE user_stats")
    op.execute("DROP TABLE llm_calls")
    op.execute("DROP TABLE worker_heartbeats")
    op.execute("DROP TABLE tasks")
    op.execute("DROP TABLE workflow_steps")
    op.execute("DROP TABLE workflow_runs")
