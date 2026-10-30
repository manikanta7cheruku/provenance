"""evidence chunks: searchable text and embeddings for each profile entry

Revision ID: 0005
Revises: 0004

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables.

evidence_chunks is tenant data. It uses the same Row Level Security policy as profile_entries:
rows are visible only when app.user_id equals the owner, and no setting yields no rows.

  text         what a person would read: one chunk per profile entry, rendered by pv_domain.evidence
  tsv          generated full-text vector (English stemming), searched with websearch_to_tsquery
  embedding    vector(768), fixed here. Changing the size needs a migration and re-embedding
               everything. NULL until the worker has embedded the chunk. NULL and its model name
               travel together.
  source_type  "profile_entry" now, "user_answer" from checkpoint 1.9. (owner, source_type,
               source_record_id) is unique, so each source has at most one chunk.

Indexes: GIN on tsv (keyword search), HNSW with cosine distance on embedding (meaning search).
A trigger removes a chunk when its profile entry is deleted, so deleting an entry always deletes the
text derived from it, whatever code path did the delete.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evidence_chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            source_type text NOT NULL CHECK (source_type IN ('profile_entry', 'user_answer')),
            source_record_id uuid NOT NULL,
            entry_type text,
            text text NOT NULL CHECK (length(text) BETWEEN 1 AND 6000),
            content_hash text NOT NULL CHECK (length(content_hash) = 64),
            embedding vector(768),
            embedding_model text CHECK (embedding_model IS NULL OR length(embedding_model) <= 120),
            embedded_at timestamptz,
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK ((embedding IS NULL) = (embedding_model IS NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX evidence_chunks_source_uniq "
        "ON evidence_chunks (owner_user_id, source_type, source_record_id)"
    )
    op.execute("CREATE INDEX evidence_chunks_tsv_idx ON evidence_chunks USING gin (tsv)")
    op.execute(
        "CREATE INDEX evidence_chunks_embedding_idx "
        "ON evidence_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX evidence_chunks_pending_idx ON evidence_chunks (owner_user_id) "
        "WHERE embedding IS NULL"
    )
    op.execute("ALTER TABLE evidence_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE evidence_chunks FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON evidence_chunks
            USING (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid)
        """
    )
    op.execute(
        """
        CREATE FUNCTION pv_delete_entry_chunk() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            DELETE FROM evidence_chunks
             WHERE owner_user_id = OLD.owner_user_id
               AND source_type = 'profile_entry'
               AND source_record_id = OLD.id;
            RETURN OLD;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER profile_entries_delete_chunk AFTER DELETE ON profile_entries
            FOR EACH ROW EXECUTE FUNCTION pv_delete_entry_chunk()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER profile_entries_delete_chunk ON profile_entries")
    op.execute("DROP FUNCTION pv_delete_entry_chunk()")
    op.execute("DROP TABLE evidence_chunks")
