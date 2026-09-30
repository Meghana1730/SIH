"""Registration and login rules.

Who may create which account:
* Anyone (not logged in): only a "candidate" account, with consent, when public registration
  is enabled (AUTH_PUBLIC_REGISTRATION). A candidate cannot link itself to a profile.
* An admin (logged in): any role, with the scope that role needs.
* The command line (app/cli/create_user.py): any role; used to create the first admin.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_config
from app.core.passwords import (
    hash_password,
    needs_rehash,
    spend_verification_time,
    verify_password,
)
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import create_access_token
from app.core.settings import Settings, get_settings
from app.models import AppUser, Candidate, District, Employer, Institute
from app.models.enums import UserRole
from app.schemas.auth import RegisterRequest
from app.services.audit import email_fingerprint, record_audit

MAX_PASSWORD_LENGTH = 128  # long enough for passphrases; bounds hashing work per request

# The scope field each role must have (admin and ssc_reviewer have none).
SCOPE_FIELD_BY_ROLE = {
    UserRole.STATE_OFFICER: "state_name",
    UserRole.DISTRICT_OFFICER: "district_id",
    UserRole.INSTITUTE_ADMIN: "institute_id",
    UserRole.EMPLOYER: "employer_id",
}
SCOPE_FIELDS = ("state_name", "district_id", "institute_id", "employer_id", "candidate_id")


class AuthError(Exception):
    """A refused auth action; the API turns it into an HTTP error with this status/code."""

    def __init__(
        self, status_code: int, code: str, message: str, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message
        self.retry_after = retry_after


# ---------------------------------------------------------------- rate limiters
@dataclass(frozen=True)
class AuthLimiters:
    login_failures_by_email: SlidingWindowLimiter
    login_attempts_by_ip: SlidingWindowLimiter
    registrations_by_ip: SlidingWindowLimiter

    def clear_all(self) -> None:
        for limiter in (
            self.login_failures_by_email,
            self.login_attempts_by_ip,
            self.registrations_by_ip,
        ):
            limiter.clear()


@lru_cache
def auth_limiters() -> AuthLimiters:
    s = get_settings()
    return AuthLimiters(
        login_failures_by_email=SlidingWindowLimiter(
            s.auth_login_max_failures, s.auth_login_window_seconds
        ),
        login_attempts_by_ip=SlidingWindowLimiter(
            s.auth_login_max_attempts_per_ip, s.auth_login_window_seconds
        ),
        registrations_by_ip=SlidingWindowLimiter(s.auth_register_max_per_ip_per_hour, 3600),
    )


# ---------------------------------------------------------------- registration
def password_problem(password: str, email: str, settings: Settings) -> str | None:
    if len(password) < settings.auth_password_min_length:
        return f"Password must be at least {settings.auth_password_min_length} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if password.strip().casefold() in {email.casefold(), email.split("@")[0].casefold()}:
        return "Password must not be your email address."
    return None


def _check_scope(db: Session, data: RegisterRequest) -> None:
    """The role's own scope field must be set (and exist); every other scope field empty."""
    role = UserRole(data.role)
    required = SCOPE_FIELD_BY_ROLE.get(role)
    allowed = {required} if required else set()
    if role is UserRole.CANDIDATE:
        allowed = {"candidate_id"}  # optional link to the candidate's own profile

    wrong = [f for f in SCOPE_FIELDS if getattr(data, f) is not None and f not in allowed]
    if wrong:
        raise AuthError(422, "SCOPE_NOT_ALLOWED", f"Role '{role}' cannot have: {', '.join(wrong)}.")
    if required and getattr(data, required) is None:
        raise AuthError(422, "SCOPE_REQUIRED", f"Role '{role}' needs '{required}'.")

    if role is UserRole.STATE_OFFICER:
        state = get_config().scope.state
        if data.state_name != state:
            raise AuthError(
                422, "UNKNOWN_STATE", f"state_name must be '{state}' in this prototype."
            )
    lookups = {
        "district_id": District,
        "institute_id": Institute,
        "employer_id": Employer,
        "candidate_id": Candidate,
    }
    for field, model in lookups.items():
        value = getattr(data, field)
        if value is not None and db.get(model, value) is None:
            raise AuthError(422, "UNKNOWN_SCOPE", f"No {model.__tablename__} with {field}={value}.")
    if data.candidate_id is not None:
        taken = db.scalar(select(AppUser.id).where(AppUser.candidate_id == data.candidate_id))
        if taken is not None:
            raise AuthError(409, "PROFILE_TAKEN", "That candidate profile already has a login.")


def create_user(
    db: Session, data: RegisterRequest, *, created_by: AppUser | None, via: str
) -> AppUser:
    """Validate, hash the password, save the user and write an audit entry.
    `via` says how the account was created: "self_service", "admin" or "cli"."""
    settings = get_settings()
    password = data.password.get_secret_value()
    if problem := password_problem(password, data.email, settings):
        raise AuthError(422, "WEAK_PASSWORD", problem)
    if db.scalar(select(AppUser.id).where(AppUser.email == data.email)) is not None:
        raise AuthError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    _check_scope(db, data)

    user = AppUser(
        email=data.email,
        password_hash=hash_password(password),
        display_name=data.display_name,
        role=UserRole(data.role).value,
        language=data.language.value,
        **{field: getattr(data, field) for field in SCOPE_FIELDS},
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        "auth.register",
        user_id=created_by.id if created_by else user.id,
        entity_type="app_user",
        entity_id=user.id,
        details={"role": user.role, "via": via, "consent": data.consent},
    )
    return user


def register(
    db: Session, data: RegisterRequest, *, actor: AppUser | None, client_ip: str
) -> AppUser:
    """The /auth/register rules: admins create any account; visitors only candidates."""
    if actor is not None:
        if actor.role != UserRole.ADMIN:
            record_audit(
                db,
                "auth.register.denied",
                user_id=actor.id,
                details={"reason": "not_admin", "requested_role": str(data.role)},
            )
            raise AuthError(403, "FORBIDDEN_ROLE", "Only an admin can create accounts for others.")
        return create_user(db, data, created_by=actor, via="admin")

    settings = get_settings()
    limiter = auth_limiters().registrations_by_ip
    if limiter.is_limited(client_ip):
        record_audit(db, "auth.rate_limited", details={"action": "register", "ip": client_ip})
        raise AuthError(
            429,
            "TOO_MANY_REQUESTS",
            "Too many sign-ups from your network. Try again later.",
            retry_after=limiter.retry_after_seconds(client_ip),
        )
    limiter.hit(client_ip)

    def deny(reason: str, status: int, code: str, message: str) -> AuthError:
        record_audit(
            db,
            "auth.register.denied",
            details={"reason": reason, "requested_role": str(data.role), "ip": client_ip},
        )
        return AuthError(status, code, message)

    if not settings.auth_public_registration:
        raise deny("public_registration_disabled", 403, "REGISTRATION_CLOSED", "Sign-up is closed.")
    if data.role != UserRole.CANDIDATE:
        raise deny(
            "staff_role_requested",
            403,
            "FORBIDDEN_ROLE",
            "Public sign-up is only for candidates. Staff accounts are created by an admin.",
        )
    if data.candidate_id is not None:
        raise deny(
            "profile_link_requested",
            403,
            "FORBIDDEN_SCOPE",
            "A candidate profile can only be linked by an admin.",
        )
    if not data.consent:
        raise AuthError(422, "CONSENT_REQUIRED", "Please accept the privacy notice (consent=true).")
    return create_user(db, data, created_by=None, via="self_service")


# ---------------------------------------------------------------- login
@dataclass(frozen=True)
class LoginResult:
    user: AppUser
    token: str
    expires_in: int


INVALID_LOGIN = "Invalid email or password."  # same message for unknown email / wrong password


def login(db: Session, email: str, password: str, *, client_ip: str) -> LoginResult:
    limiters = auth_limiters()
    by_email, by_ip = limiters.login_failures_by_email, limiters.login_attempts_by_ip
    fingerprint = email_fingerprint(email)

    for limiter, key in ((by_email, email), (by_ip, client_ip)):
        if limiter.is_limited(key):
            record_audit(
                db,
                "auth.rate_limited",
                details={"action": "login", "email_sha256": fingerprint, "ip": client_ip},
            )
            raise AuthError(
                429,
                "TOO_MANY_ATTEMPTS",
                "Too many login attempts. Try again later.",
                retry_after=limiter.retry_after_seconds(key),
            )
    by_ip.hit(client_ip)

    user = db.scalar(select(AppUser).where(AppUser.email == email))
    if user is None:
        spend_verification_time(password)
        reason = "unknown_email"
    elif not verify_password(user.password_hash, password):
        reason = "wrong_password"
    else:
        reason = None

    if reason is not None:
        by_email.hit(email)
        record_audit(
            db,
            "auth.login.failure",
            user_id=user.id if user else None,
            details={"reason": reason, "email_sha256": fingerprint, "ip": client_ip},
        )
        raise AuthError(401, "INVALID_CREDENTIALS", INVALID_LOGIN)

    assert user is not None
    if not user.is_active:
        record_audit(
            db,
            "auth.login.failure",
            user_id=user.id,
            details={"reason": "inactive", "ip": client_ip},
        )
        raise AuthError(403, "ACCOUNT_DISABLED", "This account is disabled. Contact an admin.")

    by_email.reset(email)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    token, expires_in = create_access_token(user.id, user.role)
    record_audit(db, "auth.login.success", user_id=user.id, details={"ip": client_ip})
    return LoginResult(user=user, token=token, expires_in=expires_in)
