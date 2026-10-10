"""Pure authentication rules. Standard library only.

Everything here is deterministic and unit-tested without a database or a web framework.
"""

import hashlib
import hmac
import re
import secrets

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 254

_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_COMMON_PASSWORDS = frozenset(
    {
        "password1234",
        "123456789012",
        "qwertyuiop12",
        "iloveyou1234",
        "letmein12345",
        "administrator",
        "passwordpassword",
    }
)


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def is_valid_email(email: str) -> bool:
    return len(email) <= MAX_EMAIL_LENGTH and _EMAIL_PATTERN.fullmatch(email) is not None


def password_problems(password: str, email: str | None = None) -> list[str]:
    """User-facing reasons a password is not acceptable. Empty list means acceptable."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"Use at most {MAX_PASSWORD_LENGTH} characters.")
    if len(set(password)) < 4:
        problems.append("Use a wider mix of characters.")
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("This password is too common.")
    if email:
        local_part = email.split("@")[0].lower()
        if len(local_part) >= 4 and local_part in password.lower():
            problems.append("Do not include your email name in your password.")
    return problems


def generate_token() -> str:
    """A URL-safe random token with 256 bits of entropy."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are stored only as SHA-256 hashes. They are high-entropy, so no salt is needed."""
    return hashlib.sha256(token.encode()).hexdigest()


def safe_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


def csrf_token_for(session_token: str, secret: str) -> str:
    """The CSRF token is derived from the session token, so it needs no storage."""
    return hmac.new(secret.encode(), f"csrf:{session_token}".encode(), hashlib.sha256).hexdigest()


def keyed_hash(secret: str, value: str) -> str:
    """Keyed hash for logs and audit records, so raw emails and IPs are never stored there."""
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]
