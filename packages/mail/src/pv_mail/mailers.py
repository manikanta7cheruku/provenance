"""Mail transports: SMTP for real delivery, a logger for development without SMTP.

Failures are classified so the worker knows whether retrying can help:
  retryable      network trouble, timeouts, 4xx replies, authentication problems
  not retryable  5xx replies such as "mailbox does not exist"
The summary never contains the recipient address or the message body.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from pv_config import Settings

logger = logging.getLogger("pv_mail")


class MailDeliveryError(Exception):
    def __init__(self, summary: str, *, retryable: bool) -> None:
        super().__init__(summary)
        self.summary = summary
        self.retryable = retryable


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
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._starttls = starttls
        self._sender = sender
        self._timeout = timeout

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                if self._starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if self._username:
                    smtp.login(self._username, self._password)
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            # Credentials can be fixed while the task is still retrying.
            summary = f"SMTP authentication failed ({exc.smtp_code})"
            raise MailDeliveryError(summary, retryable=True) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise MailDeliveryError("SMTP server refused the recipient", retryable=False) from exc
        except smtplib.SMTPResponseException as exc:
            retryable = exc.smtp_code < 500
            raise MailDeliveryError(f"SMTP error {exc.smtp_code}", retryable=retryable) from exc
        except (smtplib.SMTPException, OSError) as exc:
            summary = f"SMTP connection problem ({type(exc).__name__})"
            raise MailDeliveryError(summary, retryable=True) from exc


class LogMailer:
    """Development and tests only. Writes the whole email, link included, to the log.

    This is the one place a link token is logged, on purpose: it is the development
    fallback when no SMTP host is configured. Production settings require SMTP_HOST and
    this class refuses to run in production, so a real user's link can never reach a log.
    """

    def __init__(self, *, production: bool = False) -> None:
        if production:
            raise RuntimeError("LogMailer must not be used in production. Set SMTP_HOST.")

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
    return LogMailer(production=settings.environment == "production")
