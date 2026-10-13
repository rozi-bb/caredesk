"""Password hashing, sign-in tokens, and Telegram connect codes (ADR-0022, ADR-0023, ADR-0027)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ALGORITHM = "HS256"
LINK_CODE_MINUTES = 10

_hasher = PasswordHasher()
# Checked when an email is unknown, so a wrong email takes as long as a wrong
# password and response times do not reveal which emails have accounts.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    """Return a salted one-way hash of the password."""
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Return True if the password matches the hash. A missing hash never matches."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(
            password_hash
        )
    except (VerificationError, InvalidHashError):
        return False


def create_token(account_id: int, secret: str, minutes: int) -> str:
    """Return a signed token that identifies the account until it expires."""
    now = datetime.now(UTC)
    claims = {
        "sub": str(account_id),
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def read_token(token: str, secret: str) -> int | None:
    """Return the account id in a valid token, or None if it is invalid or expired."""
    try:
        claims = jwt.decode(
            token, secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]}
        )
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


def new_link_code() -> str:
    """Return a random one-time code for connecting Telegram.

    It travels in a `t.me/<bot>?start=<code>` link, so it uses only the letters,
    digits, `_` and `-` that Telegram allows there.
    """
    return secrets.token_urlsafe(16)


def hash_link_code(code: str) -> str:
    """Return the stored form of a connect code."""
    # The code is long and random, so a fast hash is enough (unlike passwords),
    # and the same code always gives the same hash, so it can be looked up.
    return hashlib.sha256(code.encode()).hexdigest()


def same_key(given: str | None, expected: str) -> bool:
    """Compare a key in constant time, so timing does not reveal how much matched."""
    return given is not None and hmac.compare_digest(given.encode(), expected.encode())
