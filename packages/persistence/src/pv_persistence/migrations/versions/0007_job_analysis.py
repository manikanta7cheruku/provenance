"""evidence check of a job: analyses, verdicts, questions and feedback

Revision ID: 0007
Revises: 0006

Every statement is a literal string (no f-strings). Default privileges from 0001 give the
application role SELECT, INSERT, UPDATE and DELETE on new tables. All four tables are tenant data
with the same Row Level Security policy as profile_entries.

  job_analyses          one per posting: where the evidence check stands. The band is NOT stored:
                        it is computed when read from the verdicts and the person's current
                        eligibility, so it can never be stale (ADR-0031, ADR-0032).
  requirement_verdicts  the agent's accepted verdict for each requirement, with the evidence it
                        cites. Each citation keeps a hash of the evidence text, so a later edit
                        to the profile is noticed.
  agent_questions       a question the agent could not answer from evidence. The answer becomes
                        evidence (evidence_chunks, source_type user_answer).
  verdict_feedback      "was this right?" answers, kept with the scoring and prompt versions.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
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
    op.execute(
        """
        CREATE TABLE job_analyses (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL UNIQUE REFERENCES job_postings (id) ON DELETE CASCADE,
            status text NOT NULL DEFAULT 'queued' CHECK (status IN (
                'queued', 'analyzing', 'needs_user_input', 'complete', 'failed'
            )),
            resume_seq integer NOT NULL DEFAULT 1 CHECK (resume_seq >= 1),
            error_code text CHECK (error_code IS NULL OR length(error_code) <= 40),
            prompt_version text,
            run_id uuid REFERENCES workflow_runs (id) ON DELETE SET NULL,
            model_calls integer NOT NULL DEFAULT 0,
            tool_calls integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz
        )
        """
    )
    _rls("job_analyses")

    op.execute(
        """
        CREATE TABLE requirement_verdicts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            analysis_id uuid NOT NULL REFERENCES job_analyses (id) ON DELETE CASCADE,
            requirement_id uuid NOT NULL REFERENCES job_requirements (id) ON DELETE CASCADE,
            verdict text NOT NULL CHECK (verdict IN (
                'met', 'partial', 'not_verified', 'conflicting'
            )),
            evidence_kind text CHECK (evidence_kind IS NULL OR evidence_kind IN (
                'direct', 'inferred'
            )),
            reason_code text CHECK (reason_code IS NULL OR length(reason_code) <= 40),
            reason text NOT NULL DEFAULT '' CHECK (length(reason) <= 300),
            citations jsonb NOT NULL DEFAULT '[]',
            capped boolean NOT NULL DEFAULT false,
            steps integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (analysis_id, requirement_id),
            CHECK (verdict = 'not_verified' OR evidence_kind IS NOT NULL)
        )
        """
    )
    _rls("requirement_verdicts")

    op.execute(
        """
        CREATE TABLE agent_questions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            analysis_id uuid NOT NULL REFERENCES job_analyses (id) ON DELETE CASCADE,
            requirement_id uuid NOT NULL REFERENCES job_requirements (id) ON DELETE CASCADE,
            question text NOT NULL CHECK (length(question) BETWEEN 1 AND 300),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN (
                'pending', 'answered', 'skipped'
            )),
            answer text CHECK (answer IS NULL OR length(answer) BETWEEN 1 AND 1000),
            created_at timestamptz NOT NULL DEFAULT now(),
            answered_at timestamptz,
            UNIQUE (analysis_id, requirement_id)
        )
        """
    )
    _rls("agent_questions")

    op.execute(
        """
        CREATE TABLE verdict_feedback (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            posting_id uuid NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
            requirement_id uuid REFERENCES job_requirements (id) ON DELETE SET NULL,
            subject text NOT NULL CHECK (subject IN ('verdict', 'recommendation')),
            shown text NOT NULL CHECK (length(shown) <= 40),
            answer text NOT NULL CHECK (answer IN ('right', 'wrong')),
            note text CHECK (note IS NULL OR length(note) <= 500),
            scoring_version text NOT NULL,
            prompt_version text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX verdict_feedback_owner_posting_idx "
        "ON verdict_feedback (owner_user_id, posting_id)"
    )
    _rls("verdict_feedback")


def downgrade() -> None:
    op.execute("DROP TABLE verdict_feedback")
    op.execute("DROP TABLE agent_questions")
    op.execute("DROP TABLE requirement_verdicts")
    op.execute("DROP TABLE job_analyses")
