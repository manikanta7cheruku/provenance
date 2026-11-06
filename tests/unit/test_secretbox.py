"""Checkpoint 3.1: a stored secret (an access token) is encrypted, authenticated and bound to what it
is for."""

import pytest

from pv_config import SecretBox, SecretBoxError

SECRET = "s" * 48


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


# ------------------------------------------------------------------ the key ring (checkpoint 3.7)

KEY_A = "a" * 40
KEY_B = "b" * 40


def test_with_a_ring_new_values_are_v2_and_name_their_key() -> None:
    from pv_config.secretbox import key_id

    box = SecretBox(SECRET, [KEY_A])
    sealed = box.seal("gho_token", context="c")
    assert box.scheme == "v2" and sealed.startswith(f"v2.{key_id(KEY_A)}.")
    assert "gho_token" not in sealed and box.open(sealed, context="c") == "gho_token"
    assert SECRET not in sealed and KEY_A not in sealed


def test_without_a_ring_values_stay_v1() -> None:
    box = SecretBox(SECRET)
    assert box.scheme == "v1" and box.seal("x", context="c").startswith("v1.")


def test_an_old_v1_value_still_opens_once_a_ring_is_added() -> None:
    old = SecretBox(SECRET).seal("token", context="c")
    box = SecretBox(SECRET, [KEY_A])
    assert box.open(old, context="c") == "token"
    assert box.needs_resealing(old)


def test_rotation_the_old_key_opens_old_values_and_the_new_key_seals_new_ones() -> None:
    sealed_with_a = SecretBox(SECRET, [KEY_A]).seal("token", context="c")
    rotated = SecretBox(SECRET, [KEY_B, KEY_A])  # new key first, old behind it
    assert rotated.open(sealed_with_a, context="c") == "token"
    assert rotated.needs_resealing(sealed_with_a)
    fresh = rotated.seal("token", context="c")
    assert not rotated.needs_resealing(fresh)
    assert (
        SecretBox(SECRET, [KEY_B]).open(fresh, context="c") == "token"
    )  # the old key is no longer needed


def test_a_value_sealed_with_a_key_that_is_gone_cannot_be_opened() -> None:
    sealed = SecretBox(SECRET, [KEY_A]).seal("token", context="c")
    with pytest.raises(SecretBoxError):
        SecretBox(SECRET, [KEY_B]).open(sealed, context="c")


def test_v2_is_bound_to_its_context_and_refuses_changes() -> None:
    box = SecretBox(SECRET, [KEY_A])
    sealed = box.seal("token", context="github-token:u1")
    with pytest.raises(SecretBoxError):
        box.open(sealed, context="github-token:u2")
    version, kid, nonce, cipher = sealed.split(".")
    flipped = cipher[:-2] + ("AA" if cipher[-2:] != "AA" else "BB")
    for bad in (
        f"{version}.{kid}.{nonce}.{flipped}",
        f"{version}.{kid}.{nonce}",
        f"v2.deadbeef.{nonce}.{cipher}",
        "v3.a.b.c",
    ):
        with pytest.raises(SecretBoxError):
            box.open(bad, context="github-token:u1")


def test_without_a_ring_nothing_needs_resealing() -> None:
    box = SecretBox(SECRET)
    assert not box.needs_resealing(box.seal("x", context="c"))


def test_keys_are_checked() -> None:
    with pytest.raises(ValueError):
        SecretBox(SECRET, ["short"])
    with pytest.raises(ValueError):
        SecretBox(SECRET, [KEY_A, KEY_A])


def test_the_ring_is_read_from_text_newest_first() -> None:
    from pv_config.secretbox import parse_ring

    assert parse_ring(f" {KEY_B} , {KEY_A} ,") == (KEY_B, KEY_A)
    assert parse_ring("") == ()
