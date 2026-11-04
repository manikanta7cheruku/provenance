"""Outgoing mail for Provenance."""

from pv_mail.delivery import DeliveryHint, delivery_hint
from pv_mail.mailers import LogMailer, MailDeliveryError, Mailer, SmtpMailer, build_mailer
from pv_mail.shortlist import ShortlistItem, render_shortlist
from pv_mail.templates import RenderedEmail, UnknownTemplateError, link_for, render_email

__all__ = [
    "DeliveryHint",
    "LogMailer",
    "MailDeliveryError",
    "Mailer",
    "RenderedEmail",
    "ShortlistItem",
    "SmtpMailer",
    "UnknownTemplateError",
    "build_mailer",
    "delivery_hint",
    "link_for",
    "render_email",
    "render_shortlist",
]
