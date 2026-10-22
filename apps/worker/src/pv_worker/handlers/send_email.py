"""Send one email. Handlers are idempotent, so this one must be safe to run twice.

Email cannot be made perfectly idempotent: if the worker dies after the SMTP server
accepted the message but before the task was marked done, the retry sends a duplicate.
That is the price of at-least-once delivery, and for "click this link" mail a duplicate
is harmless because the older link stops working when a newer token is issued.
"""

from pv_mail import MailDeliveryError, UnknownTemplateError, link_for, render_email
from pv_worker.contract import TaskContext, TaskFailure


def handle_send_email(ctx: TaskContext) -> None:
    template = ctx.args.get("template")
    to = ctx.secret.get("to")
    token = ctx.secret.get("token")
    if not (isinstance(template, str) and isinstance(to, str) and isinstance(token, str)):
        # The secret part is erased on dead-letter, so a requeued mail ends up here.
        raise TaskFailure("The email details are no longer available.", retryable=False)
    try:
        link = link_for(template, ctx.settings.public_base_url, token)
        message = render_email(template, link=link)
    except UnknownTemplateError as exc:
        raise TaskFailure("Unknown email template.", retryable=False) from exc
    try:
        ctx.mailer.send(to, message.subject, message.body)
    except MailDeliveryError as exc:
        raise TaskFailure(exc.summary, retryable=exc.retryable) from exc
