"""Handler registry. A worker only claims task types that appear here."""

from pv_domain.tasks import TASK_DEMO, TASK_PARSE_RESUME, TASK_SEND_EMAIL
from pv_worker.contract import Handler
from pv_worker.handlers.demo import handle_demo
from pv_worker.handlers.parse_resume import handle_parse_resume
from pv_worker.handlers.send_email import handle_send_email


def build_registry() -> dict[str, Handler]:
    return {
        TASK_SEND_EMAIL: handle_send_email,
        TASK_DEMO: handle_demo,
        TASK_PARSE_RESUME: handle_parse_resume,
    }
