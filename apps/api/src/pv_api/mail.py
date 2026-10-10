"""Outgoing mail. A small interface with an SMTP implementation and a development logger.

Mail is sent after the response, so response timing does not reveal whether an
account exists. Checkpoint 1.4 replaces this with the durable task queue.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from pv_config import Settings

logger = logging.getLogger("pv_api.mail")


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpMailer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        starttls: bool,
        sender: str,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._starttls = starttls
        self._sender = sender

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._starttls:
                smtp.starttls(context=ssl.create_default_context())
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)


class LogMailer:
    """Development and test only: writes the email to the application log."""

    def send(self, to: str, subject: str, body: str) -> None:
        logger.info("DEV MAIL to=%s subject=%s\n%s", to, subject, body)


def build_mailer(settings: Settings) -> Mailer:
    if settings.smtp_host:
        return SmtpMailer(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value(),
            starttls=settings.smtp_starttls,
            sender=settings.mail_from,
        )
    return LogMailer()


def _deliver(mailer: Mailer, to: str, subject: str, body: str) -> None:
    try:
        mailer.send(to, subject, body)
    except Exception:
        # The user was already answered. Record the failure so an operator can see it.
        logger.error("mail_delivery_failed", exc_info=True)


def send_verification_email(mailer: Mailer, settings: Settings, to: str, token: str) -> None:
    link = f"{settings.public_base_url}/verify-email?token={token}"
    _deliver(
        mailer,
        to,
        "Confirm your email for Provenance",
        "Open this link to confirm your email address:\n\n"
        f"{link}\n\n"
        "This link expires in 24 hours. If you did not create an account, you can ignore "
        "this message.",
    )


def send_reset_email(mailer: Mailer, settings: Settings, to: str, token: str) -> None:
    link = f"{settings.public_base_url}/reset-password?token={token}"
    _deliver(
        mailer,
        to,
        "Reset your Provenance password",
        "Open this link to choose a new password:\n\n"
        f"{link}\n\n"
        "This link expires in 1 hour and works once. If you did not ask for this, you can "
        "ignore this message. Your password has not changed.",
    )
