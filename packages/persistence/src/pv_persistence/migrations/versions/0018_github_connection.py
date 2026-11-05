"""the GitHub connection

Revision ID: 0018
Revises: 0017

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  github_connections   at most one per person. Holds who the person is on GitHub, the access
                       token encrypted (AES-GCM, bound to the person, see pv_config.secretbox)
                       and nothing else secret. `scope` is empty by design: no permission beyond
                       public data.
  github_oauth_states  one row per started sign-in. Only a hash of the random state is kept, and
                       the PKCE verifier encrypted. A row is used once and expires, so a replayed
                       or late return is refused.
  github_repos         the person's public repositories as last read, so they can choose which
                       become evidence. A copy of public facts plus a short plain excerpt of the
                       README.

All three are tenant data with Row Level Security enabled and forced, and go with the person.

An entry made from a repository has source "github" (and source_key "github:<repo id>"), so the
profile can say where it came from and a sync can find it again. The existing check on
profile_entries.source is widened to allow it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE profile_entries DROP CONSTRAINT profile_entries_source_check")
    op.execute(
        "ALTER TABLE profile_entries ADD CONSTRAINT profile_entries_source_check "
        "CHECK (source IN ('resume', 'user', 'github'))"
    )
    op.execute(
        """
        CREATE TABLE github_connections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
            github_user_id bigint NOT NULL,
            login text NOT NULL CHECK (length(login) BETWEEN 1 AND 100),
            token_sealed text NOT NULL CHECK (length(token_sealed) BETWEEN 20 AND 1000),
            scope text NOT NULL DEFAULT '' CHECK (scope = ''),
            sync_state text NOT NULL DEFAULT 'idle'
                CHECK (sync_state IN ('idle', 'queued', 'syncing', 'failed')),
            sync_error text CHECK (sync_error IS NULL OR length(sync_error) <= 300),
            connected_at timestamptz NOT NULL DEFAULT now(),
            last_synced_at timestamptz
        )
        """
    )
    op.execute(
        """
        CREATE TABLE github_oauth_states (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            state_hash text NOT NULL UNIQUE CHECK (length(state_hash) = 64),
            verifier_sealed text NOT NULL CHECK (length(verifier_sealed) BETWEEN 20 AND 1000),
            created_at timestamptz NOT NULL DEFAULT now(),
            used_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX github_oauth_states_owner_idx "
        "ON github_oauth_states (owner_user_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE github_repos (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            repo_id bigint NOT NULL,
            full_name text NOT NULL CHECK (length(full_name) BETWEEN 3 AND 140),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
            description text NOT NULL DEFAULT '' CHECK (length(description) <= 400),
            html_url text NOT NULL DEFAULT '' CHECK (length(html_url) <= 300),
            language text NOT NULL DEFAULT '' CHECK (length(language) <= 40),
            topics jsonb NOT NULL DEFAULT '[]'::jsonb,
            stars integer NOT NULL DEFAULT 0 CHECK (stars >= 0),
            fork boolean NOT NULL DEFAULT false,
            archived boolean NOT NULL DEFAULT false,
            created_remote text NOT NULL DEFAULT '',
            pushed_remote text NOT NULL DEFAULT '',
            suggested boolean NOT NULL DEFAULT false,
            selected boolean NOT NULL DEFAULT false,
            readme_excerpt text NOT NULL DEFAULT '' CHECK (length(readme_excerpt) <= 800),
            seen_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (owner_user_id, repo_id)
        )
        """
    )
    op.execute("ALTER TABLE github_connections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE github_connections FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON github_connections
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )

    op.execute("ALTER TABLE github_oauth_states ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE github_oauth_states FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON github_oauth_states
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )

    op.execute("ALTER TABLE github_repos ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE github_repos FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON github_repos
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE profile_entries SET source = 'user', source_key = NULL WHERE source = 'github'"
    )
    op.execute("ALTER TABLE profile_entries DROP CONSTRAINT profile_entries_source_check")
    op.execute(
        "ALTER TABLE profile_entries ADD CONSTRAINT profile_entries_source_check "
        "CHECK (source IN ('resume', 'user'))"
    )
    op.execute("DROP TABLE github_repos")
    op.execute("DROP TABLE github_oauth_states")
    op.execute("DROP TABLE github_connections")
