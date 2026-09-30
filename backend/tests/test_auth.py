"""Authentication (register / login / tokens) and role-based access control tests.

Everything runs against the separate test database and is rolled back after each test.
"""

import uuid
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.cli.create_user import main as create_user_cli
from app.core.passwords import hash_password, verify_password
from app.core.security import (
    SecuritySettingsError,
    check_security_settings,
    create_access_token,
)
from app.core.settings import Settings, get_settings
from app.models import (
    AppUser,
    AuditLog,
    Candidate,
    Course,
    CourseOffering,
    District,
    Employer,
    Enrollment,
    Institute,
)

pytestmark = pytest.mark.db

REGISTER, LOGIN, ME = "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/me"
PASSWORD = "Correct-Horse-Battery-9"
SYN = {"source": "TEST", "is_synthetic": True}


@pytest.fixture(scope="session")
def password_hash() -> str:
    return hash_password(PASSWORD)  # hashed once: argon2 is deliberately slow


def bearer(user: AppUser) -> dict[str, str]:
    token, _ = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def audit_entries(db, action: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def code_of(response) -> str:
    return response.json()["detail"]["code"]


@pytest.fixture
def w(db_session, password_hash) -> SimpleNamespace:
    """Two Maharashtra districts (+ one elsewhere), institutes, employers, candidates and one
    user per role."""
    s = db_session
    nashik = District(code="MH-NASHIK", name="Nashik", state_name="Maharashtra", **SYN)
    pune = District(code="MH-PUNE", name="Pune", state_name="Maharashtra", **SYN)
    other = District(code="XX-OTHER", name="Other District", state_name="Other State", **SYN)
    iti_nashik = Institute(
        code="example-iti-a", name="Example ITI A", institute_type="ITI", district=nashik, **SYN
    )
    iti_pune = Institute(
        code="example-iti-b", name="Example ITI B", institute_type="ITI", district=pune, **SYN
    )
    iti_other = Institute(
        code="example-iti-c", name="Example ITI C", institute_type="ITI", district=other, **SYN
    )
    emp_nashik = Employer(code="example-ev", name="Example EV Services", district=nashik, **SYN)
    emp_pune = Employer(code="example-solar", name="Example Solar", district=pune, **SYN)
    course = Course(code="electrician-test", name="Electrician", course_type="ITI_TRADE", **SYN)
    cand_a = Candidate(pseudonym="C-000001", district=nashik, education_level="CLASS_12", **SYN)
    cand_b = Candidate(pseudonym="C-000002", district=pune, education_level="CLASS_12", **SYN)
    for candidate, institute in ((cand_a, iti_nashik), (cand_b, iti_pune)):
        offering = CourseOffering(
            institute=institute, course=course, academic_year="2025-26", seats=40, **SYN
        )
        s.add(
            Enrollment(
                candidate=candidate, course_offering=offering, enrolled_on=date(2025, 8, 1), **SYN
            )
        )
    s.add_all([iti_other, emp_nashik, emp_pune])

    def user(email: str, role: str, **scope) -> AppUser:
        account = AppUser(
            email=email, password_hash=password_hash, display_name=role, role=role, **scope
        )
        s.add(account)
        return account

    admin = user("admin@example.test", "admin")
    state = user("state@example.test", "state_officer", state_name="Maharashtra")
    officer = user("officer.nashik@example.test", "district_officer", district=nashik)
    principal = user("principal.a@example.test", "institute_admin", institute=iti_nashik)
    ssc = user("ssc@example.test", "ssc_reviewer")
    employer = user("hr@example-ev.test", "employer", employer=emp_nashik)
    candidate = user("asha@example.test", "candidate", candidate=cand_a)
    s.flush()
    return SimpleNamespace(**locals())


# ================================================================ registration
def test_public_registration_creates_a_candidate_account(api, db_session):
    response = api.post(
        REGISTER,
        json={
            "email": " New.Person@Example.test ",
            "password": "a-long-passphrase",
            "display_name": "New Person",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "candidate"
    assert body["email"] == "new.person@example.test"  # trimmed and lower-cased
    assert not any("password" in key for key in body)  # the hash is never returned
    assert audit_entries(db_session, "auth.register")[0].diff_json["via"] == "self_service"


def test_password_is_stored_as_a_hash_never_plain_text(api, db_session):
    password = "my-secret-passphrase"
    api.post(
        REGISTER,
        json={
            "email": "hash.check@example.test",
            "password": password,
            "display_name": "Hash Check",
            "consent": True,
        },
    )
    stored = db_session.scalar(
        select(AppUser.password_hash).where(AppUser.email == "hash.check@example.test")
    )
    assert stored != password and password not in stored
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, password)
    assert not verify_password(stored, "a-different-passphrase")


def test_database_refuses_a_plain_text_password(db_session):
    db_session.add(
        AppUser(
            email="plain@example.test",
            password_hash="plain-text-password",
            display_name="Plain",
            role="ssc_reviewer",
        )
    )
    with pytest.raises(IntegrityError, match="ck_app_user_password_is_argon2_hash"):
        db_session.flush()


def test_public_registration_cannot_create_staff_accounts(api, db_session):
    response = api.post(
        REGISTER,
        json={
            "email": "sneaky@example.test",
            "password": "a-long-passphrase",
            "display_name": "Sneaky",
            "role": "admin",
            "consent": True,
        },
    )
    assert response.status_code == 403
    assert code_of(response) == "FORBIDDEN_ROLE"
    assert audit_entries(db_session, "auth.register.denied")
    assert db_session.scalar(select(AppUser).where(AppUser.email == "sneaky@example.test")) is None


def test_public_registration_needs_consent(api):
    response = api.post(
        REGISTER,
        json={
            "email": "no.consent@example.test",
            "password": "a-long-passphrase",
            "display_name": "X",
        },
    )
    assert response.status_code == 422
    assert code_of(response) == "CONSENT_REQUIRED"


def test_weak_password_is_refused_without_echoing_it(api):
    response = api.post(
        REGISTER,
        json={
            "email": "weak@example.test",
            "password": "short1",
            "display_name": "Weak",
            "consent": True,
        },
    )
    assert response.status_code == 422
    assert code_of(response) == "WEAK_PASSWORD"
    assert "short1" not in response.text


def test_duplicate_email_is_refused_even_with_different_case(api, w):
    response = api.post(
        REGISTER,
        json={
            "email": "ASHA@example.test",
            "password": "a-long-passphrase",
            "display_name": "Asha again",
            "consent": True,
        },
    )
    assert response.status_code == 409
    assert code_of(response) == "EMAIL_TAKEN"


def test_admin_creates_staff_accounts_with_the_right_scope(api, w):
    def create(**fields):
        body = {"password": PASSWORD, "display_name": "Staff", **fields}
        return api.post(REGISTER, headers=bearer(w.admin), json=body)

    ok = create(
        email="officer.pune@example.test", role="district_officer", district_id=str(w.pune.id)
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["district_id"] == str(w.pune.id)

    missing = create(email="a@example.test", role="district_officer")
    assert (missing.status_code, code_of(missing)) == (422, "SCOPE_REQUIRED")

    wrong = create(
        email="b@example.test",
        role="employer",
        employer_id=str(w.emp_pune.id),
        district_id=str(w.pune.id),
    )
    assert (wrong.status_code, code_of(wrong)) == (422, "SCOPE_NOT_ALLOWED")

    unknown = create(email="c@example.test", role="district_officer", district_id=str(uuid.uuid4()))
    assert (unknown.status_code, code_of(unknown)) == (422, "UNKNOWN_SCOPE")


def test_only_admins_create_accounts_for_others(api, w):
    response = api.post(
        REGISTER,
        headers=bearer(w.officer),
        json={
            "email": "friend@example.test",
            "password": PASSWORD,
            "display_name": "Friend",
            "role": "district_officer",
            "district_id": str(w.nashik.id),
        },
    )
    assert (response.status_code, code_of(response)) == (403, "FORBIDDEN_ROLE")


# ================================================================ login
def test_login_returns_a_token_that_works(api, w, db_session):
    response = api.post(LOGIN, json={"email": "Officer.Nashik@example.test", "password": PASSWORD})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().jwt_expires_minutes * 60
    assert body["user"]["role"] == "district_officer"

    me = api.get(ME, headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "officer.nashik@example.test"

    db_session.refresh(w.officer)
    assert w.officer.last_login_at is not None
    assert audit_entries(db_session, "auth.login.success")[0].user_id == w.officer.id


def test_wrong_password_and_unknown_email_get_the_same_answer(api, w, db_session):
    wrong = api.post(LOGIN, json={"email": w.officer.email, "password": "not-the-password"})
    unknown = api.post(LOGIN, json={"email": "nobody@example.test", "password": "whatever-1234"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no hint whether the email exists

    failures = audit_entries(db_session, "auth.login.failure")
    assert {f.diff_json["reason"] for f in failures} == {"wrong_password", "unknown_email"}
    logged = str([f.diff_json for f in failures])
    assert "not-the-password" not in logged and "nobody@example.test" not in logged


def test_disabled_account_cannot_log_in(api, w, db_session):
    w.officer.is_active = False
    db_session.flush()
    response = api.post(LOGIN, json={"email": w.officer.email, "password": PASSWORD})
    assert (response.status_code, code_of(response)) == (403, "ACCOUNT_DISABLED")


def test_repeated_failed_logins_are_rate_limited(api, w, db_session):
    for _ in range(get_settings().auth_login_max_failures):
        guess = api.post(LOGIN, json={"email": w.employer.email, "password": "wrong-guess-123"})
        assert guess.status_code == 401
    blocked = api.post(LOGIN, json={"email": w.employer.email, "password": PASSWORD})
    assert blocked.status_code == 429  # blocked even with the right password, for a while
    assert int(blocked.headers["Retry-After"]) > 0
    assert audit_entries(db_session, "auth.rate_limited")
    # Other accounts are not affected.
    assert api.post(LOGIN, json={"email": w.admin.email, "password": PASSWORD}).status_code == 200


# ================================================================ tokens
def test_protected_endpoint_without_token_is_refused(api):
    response = api.get(ME)
    assert (response.status_code, code_of(response)) == (401, "NOT_AUTHENTICATED")
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_protected_endpoint_with_token_works(api, w):
    response = api.get(ME, headers=bearer(w.ssc))
    assert response.status_code == 200
    assert response.json()["role"] == "ssc_reviewer"


def test_bad_tokens_are_rejected(api, w):
    settings = get_settings()
    secret = settings.jwt_secret.get_secret_value()
    now = datetime.now(UTC)
    claims = {
        "sub": str(w.admin.id),
        "role": "admin",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
    }
    past = now - timedelta(hours=2)
    valid, _ = create_access_token(w.admin.id, "admin")
    last = valid[-2]
    bad_tokens = {
        "expired": jwt.encode(
            {**claims, "iat": past, "nbf": past, "exp": past + timedelta(minutes=5)}, secret
        ),
        "signed with another secret": jwt.encode(claims, "another-secret-" + "x" * 32),
        "wrong audience": jwt.encode({**claims, "aud": "someone-else"}, secret),
        "unsigned (alg none)": jwt.encode(claims, None, algorithm="none"),
        "tampered": valid[:-2] + ("A" if last != "A" else "B") + valid[-1],
        "garbage": "not-a-jwt",
    }
    for name, token in bad_tokens.items():
        response = api.get(ME, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401, name
        assert code_of(response) == "INVALID_TOKEN", name
    assert api.get(ME, headers={"Authorization": f"Bearer {valid}"}).status_code == 200


def test_token_stops_working_when_the_account_is_disabled(api, w, db_session):
    headers = bearer(w.ssc)
    assert api.get(ME, headers=headers).status_code == 200
    w.ssc.is_active = False
    db_session.flush()
    assert api.get(ME, headers=headers).status_code == 401


# ================================================================ roles
def test_role_denial_is_refused_and_audited(api, w, db_session):
    response = api.get("/api/v1/admin/users", headers=bearer(w.officer))
    assert (response.status_code, code_of(response)) == (403, "FORBIDDEN_ROLE")
    denied = audit_entries(db_session, "auth.access_denied")
    assert any(d.user_id == w.officer.id and d.diff_json["reason"] == "role" for d in denied)
    assert api.get("/api/v1/admin/users", headers=bearer(w.admin)).status_code == 200


ROLE_MATRIX = {
    "/api/v1/admin/users": {"admin"},
    "/api/v1/admin/audit-log": {"admin"},
    "/api/v1/districts": {
        "admin",
        "state_officer",
        "district_officer",
        "institute_admin",
        "ssc_reviewer",
        "employer",
    },
    "/api/v1/institutes": {
        "admin",
        "state_officer",
        "district_officer",
        "institute_admin",
        "ssc_reviewer",
    },
    "/api/v1/candidates/me": {"candidate"},
}


def test_every_role_gets_exactly_its_endpoints(api, w):
    users = [w.admin, w.state, w.officer, w.principal, w.ssc, w.employer, w.candidate]
    for path, allowed in ROLE_MATRIX.items():
        for user in users:
            status = api.get(path, headers=bearer(user)).status_code
            expected = 200 if user.role in allowed else 403
            assert status == expected, f"{user.role} on {path}: got {status}"


# ================================================================ scope
def test_district_officer_only_sees_own_district(api, w):
    h = bearer(w.officer)
    assert [d["code"] for d in api.get("/api/v1/districts", headers=h).json()] == ["MH-NASHIK"]
    assert [i["code"] for i in api.get("/api/v1/institutes", headers=h).json()] == ["example-iti-a"]
    assert api.get(f"/api/v1/institutes/{w.iti_nashik.id}", headers=h).status_code == 200

    other = api.get(f"/api/v1/institutes/{w.iti_pune.id}", headers=h)
    assert (other.status_code, code_of(other)) == (403, "FORBIDDEN_SCOPE")
    assert api.get(f"/api/v1/employers/{w.emp_nashik.id}", headers=h).status_code == 200
    assert api.get(f"/api/v1/employers/{w.emp_pune.id}", headers=h).status_code == 403
    assert api.get(f"/api/v1/institutes/{uuid.uuid4()}", headers=h).status_code == 404


def test_out_of_scope_access_is_audited(api, w, db_session):
    api.get(f"/api/v1/institutes/{w.iti_pune.id}", headers=bearer(w.officer))
    denied = audit_entries(db_session, "auth.access_denied")
    assert any(
        d.diff_json["reason"] == "scope" and d.entity_id == str(w.iti_pune.id) for d in denied
    )


def test_state_officer_sees_the_whole_state_only(api, w):
    h = bearer(w.state)
    codes = {i["code"] for i in api.get("/api/v1/institutes", headers=h).json()}
    assert codes == {"example-iti-a", "example-iti-b"}  # not the other state's institute
    assert api.get(f"/api/v1/institutes/{w.iti_other.id}", headers=h).status_code == 403


def test_institute_admin_sees_own_institute_and_its_candidates(api, w):
    h = bearer(w.principal)
    assert [i["code"] for i in api.get("/api/v1/institutes", headers=h).json()] == ["example-iti-a"]
    assert api.get(f"/api/v1/institutes/{w.iti_pune.id}", headers=h).status_code == 403
    assert api.get(f"/api/v1/candidates/{w.cand_a.id}", headers=h).status_code == 200
    assert api.get(f"/api/v1/candidates/{w.cand_b.id}", headers=h).status_code == 403


def test_employer_only_sees_its_own_record(api, w):
    h = bearer(w.employer)
    own = api.get(f"/api/v1/employers/{w.emp_nashik.id}", headers=h)
    assert own.status_code == 200 and own.json()["name"] == "Example EV Services"
    other = api.get(f"/api/v1/employers/{w.emp_pune.id}", headers=h)
    assert (other.status_code, code_of(other)) == (403, "FORBIDDEN_SCOPE")
    assert code_of(api.get("/api/v1/institutes", headers=h)) == "FORBIDDEN_ROLE"
    assert api.get(f"/api/v1/candidates/{w.cand_a.id}", headers=h).status_code == 403


def test_candidate_data_is_isolated(api, w):
    h = bearer(w.candidate)
    me = api.get("/api/v1/candidates/me", headers=h)
    assert me.status_code == 200 and me.json()["pseudonym"] == "C-000001"
    assert api.get(f"/api/v1/candidates/{w.cand_a.id}", headers=h).status_code == 200
    assert api.get(f"/api/v1/candidates/{w.cand_b.id}", headers=h).status_code == 403
    # Officers, employers and SSC reviewers never see individual candidates.
    for staff in (w.officer, w.state, w.employer, w.ssc):
        assert (
            api.get(f"/api/v1/candidates/{w.cand_a.id}", headers=bearer(staff)).status_code == 403
        )


def test_self_registered_candidate_has_no_profile_until_linked(api):
    api.post(
        REGISTER,
        json={
            "email": "fresh@example.test",
            "password": "a-long-passphrase",
            "display_name": "Fresh",
            "consent": True,
        },
    )
    token = api.post(
        LOGIN, json={"email": "fresh@example.test", "password": "a-long-passphrase"}
    ).json()["access_token"]
    response = api.get("/api/v1/candidates/me", headers={"Authorization": f"Bearer {token}"})
    assert (response.status_code, code_of(response)) == (404, "NO_PROFILE")


def test_admin_can_read_the_audit_log(api, w):
    api.post(LOGIN, json={"email": w.officer.email, "password": "wrong-password-1"})
    response = api.get(
        "/api/v1/admin/audit-log", params={"action": "auth.login.failure"}, headers=bearer(w.admin)
    )
    assert response.status_code == 200
    assert response.json()[0]["details"]["reason"] == "wrong_password"


# ================================================================ setup safety
def test_app_refuses_to_run_without_a_strong_jwt_secret():
    with pytest.raises(SecuritySettingsError, match="JWT_SECRET is not set"):
        check_security_settings(Settings(_env_file=None, jwt_secret=None))
    with pytest.raises(SecuritySettingsError, match="too short"):
        check_security_settings(Settings(_env_file=None, jwt_secret="short-secret"))
    check_security_settings(Settings(_env_file=None, jwt_secret="x" * 40))


def test_no_secret_lives_in_source_code():
    assert Settings.model_fields["jwt_secret"].default is None
    secret = get_settings().jwt_secret.get_secret_value()
    backend = Path(__file__).resolve().parents[1]
    for path in [*backend.joinpath("app").rglob("*.py"), *backend.joinpath("tests").rglob("*.py")]:
        assert secret not in path.read_text(encoding="utf-8"), path


def test_cli_creates_the_first_admin(db_session):
    answers = iter([PASSWORD, PASSWORD])
    exit_code = create_user_cli(
        ["--email", "First.Admin@example.test", "--name", "First Admin", "--role", "admin"],
        ask_password=lambda _prompt: next(answers),
        open_session=lambda: nullcontext(db_session),
    )
    assert exit_code == 0
    admin = db_session.scalar(select(AppUser).where(AppUser.email == "first.admin@example.test"))
    assert admin.role == "admin" and admin.password_hash.startswith("$argon2id$")

    mismatched = iter([PASSWORD, "something-else-123"])
    assert (
        create_user_cli(
            ["--email", "second@example.test", "--name", "Second", "--role", "admin"],
            ask_password=lambda _prompt: next(mismatched),
            open_session=lambda: nullcontext(db_session),
        )
        == 1
    )
