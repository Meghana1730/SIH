"""Login tokens (JWT) and the startup check for security settings.

A JWT is a small signed text: {"sub": <user id>, "role": ..., "exp": <expiry>, ...} plus a
signature made with JWT_SECRET. Anyone can read it, but nobody can change it or create a new
one without the secret. The API checks the signature and expiry on every request, then loads
the user from the database (so a deactivated user loses access immediately).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.settings import Settings, get_settings

MIN_SECRET_LENGTH = 32
GENERATE_HINT = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


class SecuritySettingsError(Exception):
    """A security setting (e.g. JWT_SECRET) is missing or unsafe."""


class TokenError(Exception):
    """The token is malformed, expired, or not signed by this server."""


def check_security_settings(settings: Settings) -> None:
    """Called at startup: refuse to run without a strong JWT secret."""
    secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else ""
    if not secret:
        raise SecuritySettingsError(
            "JWT_SECRET is not set. Generate one (backend venv active) with:\n"
            f"  {GENERATE_HINT}\n"
            "and add the line JWT_SECRET=<value> to the .env file."
        )
    if len(secret) < MIN_SECRET_LENGTH:
        raise SecuritySettingsError(
            f"JWT_SECRET is too short ({len(secret)} characters); use at least "
            f"{MIN_SECRET_LENGTH}. Generate a new one with:\n  {GENERATE_HINT}"
        )


def _secret(settings: Settings) -> str:
    check_security_settings(settings)
    return settings.jwt_secret.get_secret_value()  # type: ignore[union-attr]


def create_access_token(
    user_id: uuid.UUID, role: str, settings: Settings | None = None
) -> tuple[str, int]:
    """Return (token, lifetime in seconds)."""
    settings = settings or get_settings()
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.jwt_expires_minutes)
    claims = {
        "sub": str(user_id),
        "role": role,  # for information only; the database role is what counts
        "iat": now,
        "nbf": now,
        "exp": now + lifetime,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(claims, _secret(settings), algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Check signature, expiry, issuer and audience. Raises TokenError if anything is wrong."""
    settings = settings or get_settings()
    try:
        return jwt.decode(
            token,
            _secret(settings),
            algorithms=[settings.jwt_algorithm],  # never accept "none" or other algorithms
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "nbf", "iss", "aud"]},
            leeway=10,  # seconds of tolerance for small clock differences
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError(str(exc)) from None
