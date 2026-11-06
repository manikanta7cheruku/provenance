"""Encrypt small secrets (an access token) before they are stored, and decrypt them when used.

AES-256-GCM with a fresh random 96-bit nonce for every seal, and the *context* (what the secret is
for and whose it is) authenticated as associated data. Two properties follow:

  - a stored value that was changed is refused (GCM authenticates it);
  - a stored value moved to another row or another person fails to open, because the context is
    part of what is authenticated.

Two key schemes, told apart by a version prefix so a key can change without guessing what an old
value is:

  v1.<nonce>.<ciphertext>          the key is derived from the application secret (SECRET_KEY).
                                   Rotating SECRET_KEY would make every v1 value unreadable.
  v2.<keyid>.<nonce>.<ciphertext>  the key is one of a ring of dedicated token keys
                                   (TOKEN_ENCRYPTION_KEYS). The first key seals, every key in the
                                   ring opens, and `keyid` says which one a value was sealed with.

Rotation without losing anything: add the new key at the front of the ring, keep the old one behind
it, restart, re-seal stored values (`pv_api.cli reseal-tokens`), then drop the old key. A value
sealed with a key that is no longer in the ring cannot be opened, by design: losing every key means
losing the tokens, and the person reconnects.
"""

import base64
import hashlib
import os
from collections.abc import Sequence

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_V1 = "v1"
_V2 = "v2"
_PURPOSE_V1 = b"provenance/secretbox/v1"
_PURPOSE_V2 = b"provenance/secretbox/v2"
_NONCE_BYTES = 12
MIN_KEY_LENGTH = 32


class SecretBoxError(Exception):
    """A stored secret could not be opened: it was changed, moved, or sealed with another key."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _derive(secret: str, purpose: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=purpose).derive(
        secret.encode("utf-8")
    )


def key_id(secret: str) -> str:
    """A short public name for a key, so a value says which key sealed it without revealing it."""
    return hashlib.sha256(b"provenance/keyid/" + secret.encode("utf-8")).hexdigest()[:8]


def parse_ring(text: str) -> tuple[str, ...]:
    """The keys in a TOKEN_ENCRYPTION_KEYS value: comma separated, newest first."""
    return tuple(part.strip() for part in text.split(",") if part.strip())


class SecretBox:
    def __init__(self, secret: str, keys: Sequence[str] = ()) -> None:
        if len(secret) < MIN_KEY_LENGTH:
            raise ValueError("the application secret is too short to derive a key from")
        for key in keys:
            if len(key) < MIN_KEY_LENGTH:
                raise ValueError(
                    f"every token encryption key must be at least {MIN_KEY_LENGTH} characters"
                )
        if len(set(keys)) != len(keys):
            raise ValueError("a token encryption key appears twice in the ring")
        self._v1 = AESGCM(_derive(secret, _PURPOSE_V1))
        self._ring = {key_id(k): AESGCM(_derive(k, _PURPOSE_V2)) for k in keys}
        self._newest = key_id(keys[0]) if keys else None

    @classmethod
    def for_settings(cls, settings: "object") -> "SecretBox":
        """The box an application process uses: the secret for old values, the ring for new ones."""
        secret = settings.secret_key.get_secret_value()  # type: ignore[attr-defined]
        ring = parse_ring(settings.token_encryption_keys.get_secret_value())  # type: ignore[attr-defined]
        return cls(secret, ring)

    @property
    def scheme(self) -> str:
        """The version new values are sealed with."""
        return _V2 if self._newest else _V1

    def seal(self, plaintext: str, *, context: str) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        aad = context.encode("utf-8")
        if self._newest is None:
            ciphertext = self._v1.encrypt(nonce, plaintext.encode("utf-8"), aad)
            return f"{_V1}.{_b64(nonce)}.{_b64(ciphertext)}"
        ciphertext = self._ring[self._newest].encrypt(nonce, plaintext.encode("utf-8"), aad)
        return f"{_V2}.{self._newest}.{_b64(nonce)}.{_b64(ciphertext)}"

    def open(self, sealed: str, *, context: str) -> str:
        aad = context.encode("utf-8")
        try:
            parts = sealed.split(".")
            if parts[0] == _V1 and len(parts) == 3:
                plaintext = self._v1.decrypt(_unb64(parts[1]), _unb64(parts[2]), aad)
            elif parts[0] == _V2 and len(parts) == 4:
                aead = self._ring.get(parts[1])
                if aead is None:
                    raise SecretBoxError("sealed with a key that is not in the ring")
                plaintext = aead.decrypt(_unb64(parts[2]), _unb64(parts[3]), aad)
            else:
                raise SecretBoxError("unknown version")
        except (ValueError, InvalidTag) as exc:
            raise SecretBoxError("the stored secret could not be opened") from exc
        return plaintext.decode("utf-8")

    def needs_resealing(self, sealed: str) -> bool:
        """True when a stored value is not sealed with the newest key, so rotation can finish."""
        parts = sealed.split(".")
        if self._newest is None:
            return False
        return not (parts[0] == _V2 and len(parts) == 4 and parts[1] == self._newest)
