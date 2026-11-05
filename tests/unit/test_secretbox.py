"""Checkpoint 3.1: a stored secret (an access token) is encrypted, authenticated and bound to what it
is for."""

import pytest

from pv_config import SecretBox, SecretBoxError

SECRET = "a-long-enough-application-secret-for-tests-0123456789"


def test_a_secret_round_trips_and_is_not_stored_in_clear() -> None:
    box = SecretBox(SECRET)
    sealed = box.seal("gho_exampletoken", context="github-token:user-1")
    assert "gho_exampletoken" not in sealed
    assert sealed.startswith("v1.")
    assert box.open(sealed, context="github-token:user-1") == "gho_exampletoken"


def test_every_seal_is_different() -> None:
    box = SecretBox(SECRET)
    assert box.seal("same", context="c") != box.seal("same", context="c")


def test_a_secret_cannot_be_opened_for_another_context() -> None:
    box = SecretBox(SECRET)
    sealed = box.seal("token", context="github-token:user-1")
    with pytest.raises(SecretBoxError):
        box.open(sealed, context="github-token:user-2")


def test_a_changed_secret_is_refused() -> None:
    box = SecretBox(SECRET)
    sealed = box.seal("token", context="c")
    version, nonce, cipher = sealed.split(".")
    flipped = cipher[:-2] + ("AA" if cipher[-2:] != "AA" else "BB")
    for bad in (
        f"{version}.{nonce}.{flipped}",
        f"{version}.{nonce}.",
        "v1.x",
        "",
        "v2.a.b",
        "garbage",
    ):
        with pytest.raises(SecretBoxError):
            box.open(bad, context="c")


def test_another_key_cannot_open_it() -> None:
    sealed = SecretBox(SECRET).seal("token", context="c")
    with pytest.raises(SecretBoxError):
        SecretBox(SECRET + "x").open(sealed, context="c")


def test_a_short_application_secret_is_refused() -> None:
    with pytest.raises(ValueError):
        SecretBox("short")


def test_unicode_survives() -> None:
    box = SecretBox(SECRET)
    assert box.open(box.seal("tökén ✓", context="c"), context="c") == "tökén ✓"
