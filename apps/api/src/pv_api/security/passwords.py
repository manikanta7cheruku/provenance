"""Password hashing with Argon2id.

argon2-cffi's PasswordHasher defaults to Argon2id with the RFC 9106 low-memory
parameters (3 iterations, 64 MiB, 4 lanes). The cost is deliberate: it makes offline
guessing expensive. Parameters are re-checked on each login and upgraded when the
library's recommended parameters change.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Used so that an unknown email costs the same time as a wrong password.
_DUMMY_HASH = _hasher.hash("timing-equalization-placeholder")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_dummy(password: str) -> bool:
    verify_password(_DUMMY_HASH, password)
    return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
