"""pictures for the resume studio

Revision ID: 0016
Revises: 0015

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

  resume_images   one row per stored picture. The bytes live in private storage under `storage_key`;
                  the row says what they are. What is stored is never what was uploaded: it was
                  decoded and drawn again as a fresh JPEG or PNG with no metadata and cut down to a
                  size a resume needs. `sha256` is of the stored bytes, so the same picture
                  uploaded twice is one row. The table is tenant data with Row Level Security
                  enabled and forced, and goes with the person. A resume refers to a picture by id,
                  and a save is refused when the id is not the person's own.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE resume_images (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            storage_key text NOT NULL CHECK (length(storage_key) <= 100),
            mime text NOT NULL CHECK (mime IN ('image/jpeg', 'image/png')),
            width integer NOT NULL CHECK (width BETWEEN 1 AND 4000),
            height integer NOT NULL CHECK (height BETWEEN 1 AND 4000),
            size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 20000000),
            original_name text NOT NULL DEFAULT '' CHECK (length(original_name) <= 120),
            sha256 text NOT NULL CHECK (length(sha256) = 64),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX resume_images_owner_hash_uniq ON resume_images (owner_user_id, sha256)"
    )
    op.execute(
        "CREATE INDEX resume_images_owner_created_idx ON resume_images (owner_user_id, created_at DESC)"
    )
    op.execute("ALTER TABLE resume_images ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE resume_images FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON resume_images
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE resume_images")
