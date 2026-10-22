"""Email templates. Plain text on purpose: no tracking pixels, nothing to render wrongly."""

from dataclasses import dataclass


class UnknownTemplateError(ValueError):
    pass


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    body: str


_PATHS = {"verify": "/verify-email", "reset": "/reset-password"}


def link_for(template: str, public_base_url: str, token: str) -> str:
    try:
        path = _PATHS[template]
    except KeyError as exc:
        raise UnknownTemplateError(template) from exc
    return f"{public_base_url.rstrip('/')}{path}?token={token}"


def render_email(template: str, *, link: str) -> RenderedEmail:
    if template == "verify":
        return RenderedEmail(
            subject="Confirm your email for Provenance",
            body=(
                "Open this link to confirm your email address:\n\n"
                f"{link}\n\n"
                "This link expires in 24 hours. If you did not create an account, you can "
                "ignore this message."
            ),
        )
    if template == "reset":
        return RenderedEmail(
            subject="Reset your Provenance password",
            body=(
                "Open this link to choose a new password:\n\n"
                f"{link}\n\n"
                "This link expires in 1 hour and works once. If you did not ask for this, "
                "you can ignore this message. Your password has not changed."
            ),
        )
    raise UnknownTemplateError(template)
