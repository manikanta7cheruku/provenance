import smtplib
from collections.abc import Callable
from typing import Any

import pytest

from pv_config import Settings
from pv_mail import (
    LogMailer,
    MailDeliveryError,
    SmtpMailer,
    UnknownTemplateError,
    build_mailer,
    delivery_hint,
    link_for,
    render_email,
)

Make = Callable[..., Settings]

PRODUCTION = {
    "environment": "production",
    "cors_origins": "https://app.example.org",
    "public_base_url": "https://app.example.org",
    "smtp_host": "smtp.example.org",
}


def test_log_mailer_is_used_without_smtp_host(make_settings: Make) -> None:
    assert isinstance(build_mailer(make_settings()), LogMailer)


def test_smtp_mailer_is_used_with_smtp_host(make_settings: Make) -> None:
    assert isinstance(build_mailer(make_settings(smtp_host="mailpit", smtp_port=1025)), SmtpMailer)


def test_log_mailer_refuses_to_run_in_production() -> None:
    with pytest.raises(RuntimeError):
        LogMailer(production=True)


def test_link_and_templates() -> None:
    link = link_for("verify", "http://localhost:5173/", "tok123")
    assert link == "http://localhost:5173/verify-email?token=tok123"
    assert link_for("reset", "http://x", "t") == "http://x/reset-password?token=t"
    message = render_email("reset", link=link)
    assert link in message.body
    assert "Provenance" in message.subject


def test_unknown_template_is_rejected() -> None:
    with pytest.raises(UnknownTemplateError):
        render_email("nope", link="x")
    with pytest.raises(UnknownTemplateError):
        link_for("nope", "http://x", "t")


def test_delivery_hint_log_mode_tells_the_truth(make_settings: Make) -> None:
    hint = delivery_hint(make_settings(smtp_host=""))
    assert hint.mode == "log"
    assert "not sent" in hint.text
    assert "worker log" in hint.text


def test_delivery_hint_development_smtp_points_at_the_local_inbox(make_settings: Make) -> None:
    hint = delivery_hint(make_settings(smtp_host="mailpit", dev_inbox_url="http://localhost:8025"))
    assert hint.mode == "smtp_dev"
    assert "http://localhost:8025" in hint.text
    assert "queued" in hint.text


def test_delivery_hint_production_does_not_mention_the_dev_inbox(make_settings: Make) -> None:
    hint = delivery_hint(make_settings(**PRODUCTION))
    assert hint.mode == "smtp"
    assert "localhost" not in hint.text
    assert "queued" in hint.text


class _FailingSmtp:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise self._error


def _send_with(monkeypatch: pytest.MonkeyPatch, error: Exception) -> MailDeliveryError:
    monkeypatch.setattr("pv_mail.mailers.smtplib.SMTP", _FailingSmtp(error))
    mailer = SmtpMailer(
        host="h", port=25, username="", password="", starttls=False, sender="a@localhost"
    )
    with pytest.raises(MailDeliveryError) as caught:
        mailer.send("someone@example.com", "s", "b")
    return caught.value


def test_connection_problems_are_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    error = _send_with(monkeypatch, ConnectionRefusedError("no"))
    assert error.retryable is True


def test_temporary_smtp_replies_are_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    error = _send_with(monkeypatch, smtplib.SMTPResponseException(451, b"try later"))
    assert error.retryable is True
    assert "451" in error.summary


def test_permanent_smtp_replies_are_not_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    error = _send_with(monkeypatch, smtplib.SMTPResponseException(550, b"no mailbox"))
    assert error.retryable is False


def test_refused_recipient_is_not_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    error = _send_with(
        monkeypatch, smtplib.SMTPRecipientsRefused({"someone@example.com": (550, b"x")})
    )
    assert error.retryable is False


def test_authentication_problems_are_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    error = _send_with(monkeypatch, smtplib.SMTPAuthenticationError(535, b"bad credentials"))
    assert error.retryable is True


def test_failure_summaries_never_contain_the_address(monkeypatch: pytest.MonkeyPatch) -> None:
    error = _send_with(
        monkeypatch, smtplib.SMTPRecipientsRefused({"someone@example.com": (550, b"x")})
    )
    assert "someone@example.com" not in error.summary
