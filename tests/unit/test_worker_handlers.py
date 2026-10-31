import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

import pytest

from pv_config import Settings
from pv_mail import MailDeliveryError
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers import build_registry
from pv_worker.handlers.demo import handle_demo
from pv_worker.handlers.send_email import handle_send_email
from pv_worker.logging_config import JsonFormatter

Make = Callable[..., Settings]


class _Mailer:
    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self._error = error

    def send(self, to: str, subject: str, body: str) -> None:
        if self._error:
            raise self._error
        self.sent.append((to, subject, body))


def _context(
    settings: Settings, mailer: _Mailer, args: dict[str, Any], secret: dict[str, Any]
) -> TaskContext:
    return TaskContext(
        task_id=uuid.uuid4(),
        task_type="send_email",
        args=args,
        secret=secret,
        attempt=1,
        max_attempts=5,
        owner_user_id=None,
        run_id=None,
        settings=settings,
        engine=None,  # type: ignore[arg-type]
        mailer=mailer,
        extend_lease=lambda: True,
    )


def test_registry_knows_the_task_types() -> None:
    assert set(build_registry()) == {
        "send_email",
        "system.demo",
        "parse_resume",
        "embed_evidence",
        "extract_job",
        "analyze_job",
        "render_resume_pdf",
    }


def test_send_email_renders_the_link_and_sends(make_settings: Make) -> None:
    mailer = _Mailer()
    ctx = _context(
        make_settings(public_base_url="http://localhost:5173"),
        mailer,
        {"template": "verify"},
        {"to": "ada@example.com", "token": "abc123"},
    )
    handle_send_email(ctx)
    assert mailer.sent[0][0] == "ada@example.com"
    assert "http://localhost:5173/verify-email?token=abc123" in mailer.sent[0][2]


def test_send_email_without_its_secret_fails_permanently(make_settings: Make) -> None:
    ctx = _context(make_settings(), _Mailer(), {"template": "verify"}, {})
    with pytest.raises(TaskFailure) as caught:
        handle_send_email(ctx)
    assert caught.value.retryable is False


def test_send_email_with_unknown_template_fails_permanently(make_settings: Make) -> None:
    ctx = _context(make_settings(), _Mailer(), {"template": "x"}, {"to": "a@b.co", "token": "t"})
    with pytest.raises(TaskFailure) as caught:
        handle_send_email(ctx)
    assert caught.value.retryable is False


@pytest.mark.parametrize("retryable", [True, False])
def test_mail_delivery_errors_keep_their_retry_class(make_settings: Make, retryable: bool) -> None:
    mailer = _Mailer(MailDeliveryError("SMTP error", retryable=retryable))
    ctx = _context(make_settings(), mailer, {"template": "reset"}, {"to": "a@b.co", "token": "t"})
    with pytest.raises(TaskFailure) as caught:
        handle_send_email(ctx)
    assert caught.value.retryable is retryable
    assert "a@b.co" not in str(caught.value)


@pytest.mark.parametrize(
    "args", [{}, {"seconds": "5", "marker": "m"}, {"seconds": 5000, "marker": "m"}, {"seconds": 1}]
)
def test_demo_rejects_bad_arguments(make_settings: Make, args: dict[str, Any]) -> None:
    ctx = _context(make_settings(), _Mailer(), args, {})
    with pytest.raises(TaskFailure) as caught:
        handle_demo(ctx)
    assert caught.value.retryable is False


def test_json_log_format_includes_extras_and_is_one_line() -> None:
    record = logging.LogRecord("pv_worker", logging.INFO, "f", 1, "task_finished", (), None)
    record.task_id = "abc"
    record.outcome = "succeeded"
    line = JsonFormatter().format(record)
    data = json.loads(line)
    assert data["message"] == "task_finished"
    assert data["task_id"] == "abc"
    assert "\n" not in line
