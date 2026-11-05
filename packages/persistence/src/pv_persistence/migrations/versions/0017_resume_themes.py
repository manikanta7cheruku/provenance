"""saved themes for the resume studio

Revision ID: 0017
Revises: 0016

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  resume_themes   a named font pair and four colors a person reuses across resumes. A theme holds
                  the look only, no words and no pictures. Names are unique per person ignoring
                  case. The table is tenant data with Row Level Security enabled and forced, and
                  goes with the person. The colors are hex codes by a CHECK; whether they are
                  readable together is decided in pv_domain.resume_themes before a row is written.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE resume_themes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
            font_pair text NOT NULL CHECK (length(font_pair) BETWEEN 1 AND 40),
            accent text NOT NULL CHECK (accent ~ '^#[0-9a-f]{6}$'),
            ink text NOT NULL CHECK (ink ~ '^#[0-9a-f]{6}$'),
            muted text NOT NULL CHECK (muted ~ '^#[0-9a-f]{6}$'),
            tint text NOT NULL CHECK (tint ~ '^#[0-9a-f]{6}$'),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX resume_themes_owner_name_uniq "
        "ON resume_themes (owner_user_id, lower(name))"
    )
    op.execute("ALTER TABLE resume_themes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE resume_themes FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON resume_themes
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE resume_themes")
