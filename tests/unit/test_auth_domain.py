import pytest

from pv_domain.auth import (
    csrf_token_for,
    generate_token,
    hash_token,
    is_valid_email,
    keyed_hash,
    normalize_email,
    password_problems,
    safe_equals,
)
from pv_domain.ratelimit import DEFAULT_POLICIES


def test_email_is_normalized() -> None:
    assert normalize_email("  Ada@Example.COM ") == "ada@example.com"


@pytest.mark.parametrize("email", ["ada@example.com", "a.b+c@sub.example.org"])
def test_valid_emails(email: str) -> None:
    assert is_valid_email(email)


@pytest.mark.parametrize(
    "email",
    ["", "ada", "ada@", "@example.com", "ada@example", "a b@example.com", "x" * 250 + "@e.co"],
)
def test_invalid_emails(email: str) -> None:
    assert not is_valid_email(email)


def test_strong_password_has_no_problems() -> None:
    assert password_problems("correct horse battery staple", "ada@example.com") == []


def test_short_password_is_rejected() -> None:
    assert any("at least 12" in p for p in password_problems("short"))


def test_common_password_is_rejected() -> None:
    assert any("too common" in p for p in password_problems("password1234"))


def test_password_containing_email_name_is_rejected() -> None:
    problems = password_problems("ada.lovelace-is-great", "ada.lovelace@example.com")
    assert any("email name" in p for p in problems)


def test_repetitive_password_is_rejected() -> None:
    assert password_problems("aaaaaaaaaaaaaaaa")


def test_tokens_are_unique_and_long() -> None:
    first, second = generate_token(), generate_token()
    assert first != second
    assert len(first) >= 43


def test_token_hash_is_deterministic_and_not_the_token() -> None:
    token = generate_token()
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64


def test_csrf_token_depends_on_session_and_secret() -> None:
    base = csrf_token_for("session-a", "secret-one")
    assert base == csrf_token_for("session-a", "secret-one")
    assert base != csrf_token_for("session-b", "secret-one")
    assert base != csrf_token_for("session-a", "secret-two")


def test_safe_equals() -> None:
    assert safe_equals("abc", "abc")
    assert not safe_equals("abc", "abd")


def test_keyed_hash_does_not_expose_input() -> None:
    value = keyed_hash("secret", "ada@example.com")
    assert "ada" not in value
    assert value == keyed_hash("secret", "ada@example.com")
    assert value != keyed_hash("other-secret", "ada@example.com")


def test_default_rate_policies_are_sane() -> None:
    assert DEFAULT_POLICIES["login_ip"].limit == 5
    assert DEFAULT_POLICIES["login_ip"].window_seconds == 60
    for name, policy in DEFAULT_POLICIES.items():
        assert policy.name == name
        assert policy.limit > 0
        assert policy.window_seconds > 0
