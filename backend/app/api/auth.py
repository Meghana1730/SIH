"""/api/v1/auth: register, login, me."""

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import CurrentUser, DbSession, OptionalUser, client_ip, error
from app.models import AppUser
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import auth as auth_service
from app.services.auth import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


def _http(exc: AuthError) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else {}
    return error(exc.status_code, exc.code, exc.message, **headers)


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    body: RegisterRequest, request: Request, db: DbSession, actor: OptionalUser
) -> AppUser:
    """Create an account.

    * Not logged in: creates a **candidate** account (needs `consent: true`).
    * Logged in as **admin**: creates any role; set the scope field that role needs
      (`state_name`, `district_id`, `institute_id`, `employer_id` or `candidate_id`).
    """
    try:
        user = auth_service.register(db, body, actor=actor, client_ip=client_ip(request))
    except AuthError as exc:
        raise _http(exc) from None
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    """Exchange email + password for an access token (send it as `Authorization: Bearer ...`)."""
    try:
        result = auth_service.login(
            db, body.email, body.password.get_secret_value(), client_ip=client_ip(request)
        )
    except AuthError as exc:
        raise _http(exc) from None
    db.commit()
    return TokenResponse(
        access_token=result.token,
        expires_in=result.expires_in,
        user=UserResponse.model_validate(result.user),
    )


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> AppUser:
    """The logged-in user."""
    return user
