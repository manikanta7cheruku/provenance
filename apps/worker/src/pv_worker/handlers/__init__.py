"""Handler registry. A worker only claims task types that appear here."""

from pv_domain.tasks import (
    TASK_ANALYZE_JOB,
    TASK_DEMO,
    TASK_EMBED_EVIDENCE,
    TASK_EXTRACT_JOB,
    TASK_PARSE_RESUME,
    TASK_RENDER_RESUME,
    TASK_SEND_EMAIL,
    TASK_TAILOR_RESUME,
)
from pv_worker.contract import Handler
from pv_worker.handlers.analyze_job import handle_analyze_job
from pv_worker.handlers.demo import handle_demo
from pv_worker.handlers.embed_evidence import handle_embed_evidence
from pv_worker.handlers.extract_job import handle_extract_job
from pv_worker.handlers.parse_resume import handle_parse_resume
from pv_worker.handlers.render_resume import handle_render_resume
from pv_worker.handlers.send_email import handle_send_email
from pv_worker.handlers.tailor_resume import handle_tailor_resume


def build_registry() -> dict[str, Handler]:
    return {
        TASK_SEND_EMAIL: handle_send_email,
        TASK_DEMO: handle_demo,
        TASK_PARSE_RESUME: handle_parse_resume,
        TASK_EMBED_EVIDENCE: handle_embed_evidence,
        TASK_EXTRACT_JOB: handle_extract_job,
        TASK_ANALYZE_JOB: handle_analyze_job,
        TASK_RENDER_RESUME: handle_render_resume,
        TASK_TAILOR_RESUME: handle_tailor_resume,
    }
