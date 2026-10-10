"""identity, sessions, tokens, invites, audit, rate limits, first tenant table with RLS

Revision ID: 0002
Revises: 0001

Every statement is a literal string. Default privileges from 0001 give the application
role SELECT, INSERT, UPDATE and DELETE on new tables. This migration then narrows that
where the design requires it (the audit log is append-only).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email citext NOT NULL UNIQUE,
            password_hash text NOT NULL,
            role text NOT NULL DEFAULT 'USER' CHECK (role IN ('USER', 'ADMIN')),
            email_verified_at timestamptz,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            token_hash text NOT NULL UNIQUE,
            user_agent_hash text,
            created_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz
        )
        """
    )
    op.execute("CREATE INDEX sessions_user_id_idx ON sessions (user_id)")
    op.execute(
        """
        CREATE TABLE email_tokens (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            purpose text NOT NULL CHECK (purpose IN ('verify', 'reset')),
            token_hash text NOT NULL UNIQUE,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX email_tokens_user_idx ON email_tokens (user_id, purpose)")
    op.execute(
        """
        CREATE TABLE invites (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code_hash text NOT NULL UNIQUE,
            email citext,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            used_by uuid REFERENCES users (id) ON DELETE SET NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE audit_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            category text NOT NULL CHECK (category IN ('audit', 'security')),
            action text NOT NULL,
            actor_user_id uuid REFERENCES users (id) ON DELETE SET NULL,
            target_type text,
            target_id text,
            ip_hash text,
            metadata jsonb NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX audit_events_created_idx ON audit_events (created_at DESC)")
    # Append-only: the application can write and read the audit log but never change it.
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM provenance_app")

    op.execute(
        """
        CREATE TABLE rate_limit_buckets (
            bucket_key text NOT NULL,
            window_start timestamptz NOT NULL,
            hits integer NOT NULL,
            PRIMARY KEY (bucket_key, window_start)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE profile_entries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            entry_type text NOT NULL CHECK (entry_type IN (
                'education', 'work', 'internship', 'project',
                'skill', 'certification', 'achievement', 'link'
            )),
            data jsonb NOT NULL DEFAULT '{}',
            user_edited boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX profile_entries_owner_idx ON profile_entries (owner_user_id, entry_type)"
    )
    # Tenant isolation: rows are visible only when app.user_id (set per transaction by the
    # API) equals the owner. With no setting the policy yields no rows (fail closed).
    op.execute("ALTER TABLE profile_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE profile_entries FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON profile_entries
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE profile_entries")
    op.execute("DROP TABLE rate_limit_buckets")
    op.execute("DROP TABLE audit_events")
    op.execute("DROP TABLE invites")
    op.execute("DROP TABLE email_tokens")
    op.execute("DROP TABLE sessions")
    op.execute("DROP TABLE users")
