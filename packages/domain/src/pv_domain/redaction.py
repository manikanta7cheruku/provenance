"""Safe error text. Anything stored or logged about a failure passes through here.

Failure text must never carry an email address or a token-like string, because task
errors are visible to administrators and end up in logs. This is defense in depth:
handlers are also expected not to put such values in their messages.
"""

import re

MAX_ERROR_LENGTH = 300

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_TOKENISH = re.compile(r"[A-Za-z0-9_-]{24,}")


def redact(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    return _TOKENISH.sub("[redacted]", text)


def error_summary(error_type: str, message: str, *, limit: int = MAX_ERROR_LENGTH) -> str:
    """'ErrorType: message' with PII and token-like strings removed, at most `limit` characters."""
    summary = redact(f"{error_type}: {message}".strip())
    if len(summary) <= limit:
        return summary
    return summary[: limit - 3] + "..."
