"""Encrypt small secrets (an access token) before they are stored, and decrypt them when used.

AES-256-GCM with a key derived from the application secret (HKDF-SHA256, a fixed purpose string),
a fresh random 96-bit nonce for every seal, and the *context* (what the secret is for and whose it
is) authenticated as associated data. Two properties follow:

  - a stored value that was changed is refused (GCM authenticates it);
  - a stored value moved to another row or another person fails to open, because the context is
    part of what is authenticated.

The result is a short text: `v1.<nonce>.<ciphertext>` in URL-safe base64. The version prefix lets
the key or the scheme change later without guessing what an old value is.
"""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_VERSION = "v1"
_PURPOSE = b"provenance/secretbox/v1"
_NONCE_BYTES = 12


class SecretBoxError(Exception):
    """A stored secret could not be opened: it was changed, moved, or sealed with another key."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class SecretBox:
    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise ValueError("the application secret is too short to derive a key from")
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_PURPOSE).derive(
            secret.encode("utf-8")
        )
        self._aead = AESGCM(key)

    def seal(self, plaintext: str, *, context: str) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aead.encrypt(nonce, plaintext.encode("utf-8"), context.encode("utf-8"))
        return f"{_VERSION}.{_b64(nonce)}.{_b64(ciphertext)}"

    def open(self, sealed: str, *, context: str) -> str:
        try:
            version, nonce_text, cipher_text = sealed.split(".")
            if version != _VERSION:
                raise SecretBoxError("unknown version")
            plaintext = self._aead.decrypt(
                _unb64(nonce_text), _unb64(cipher_text), context.encode("utf-8")
            )
        except (ValueError, InvalidTag) as exc:
            raise SecretBoxError("the stored secret could not be opened") from exc
        return plaintext.decode("utf-8")
