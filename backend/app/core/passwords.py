"""Password hashing with argon2id.

A hash is a one-way scramble: we can check whether a typed password matches it, but nobody
(including us) can turn it back into the password. Plain-text passwords are never stored or
logged, and the database refuses any value that is not an argon2id hash.
"""

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2id with the library's recommended settings (RFC 9106 "low memory" profile:
# 3 passes, 64 MiB memory, 4 lanes). Each hash takes a fraction of a second on purpose,
# which makes guessing stolen hashes very slow.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the hash was made with older settings and should be upgraded at next login."""
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash("dummy-password-for-timing")


def spend_verification_time(password: str) -> None:
    """Verify against a dummy hash, so a login with an unknown email takes as long as one with
    a wrong password (attackers cannot find valid emails by timing responses)."""
    verify_password(_dummy_hash(), password)
