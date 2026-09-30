"""Create the demo accounts shown on the frontend login page (one per role, all is_demo=true):

    python -m app.cli.demo_users

The password for every demo account is read from the DEMO_USER_PASSWORD environment variable
(or asked twice when it is not set). It is never stored in source code. Accounts that already
exist are left unchanged, so running this again is safe.
"""

import getpass
import os
import sys

from pydantic import ValidationError
from sqlalchemy import select

from app.config import get_config
from app.core.db import SessionLocal
from app.models import AppUser, District, Employer, Institute
from app.schemas.auth import RegisterRequest
from app.services.auth import AuthError, create_user

# (email, display name, role, scope field, scope code). Scope codes are demo-world records.
DEMO_ACCOUNTS = [
    ("admin@kaushalsetu.example", "Demo Platform Admin", "admin", None, None),
    ("state@kaushalsetu.example", "Demo State Officer", "state_officer", "state_name", None),
    ("nashik@kaushalsetu.example", "Demo District Officer, Nashik", "district_officer",
     "district_id", "MH-NASHIK"),
    ("institute@kaushalsetu.example", "Demo Principal, Example ITI A", "institute_admin",
     "institute_id", "EX-ITI-A"),
    ("employer@kaushalsetu.example", "Demo HR, Example EV Service Hub", "employer",
     "employer_id", "EX-EMP-NSK-01"),
    ("candidate@kaushalsetu.example", "Demo Candidate", "candidate", None, None),
]  # fmt: skip


def _password() -> str | None:
    password = os.environ.get("DEMO_USER_PASSWORD")
    if password:
        return password
    password = getpass.getpass("Password for the demo accounts: ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match. Nothing was created.", file=sys.stderr)
        return None
    return password


def main() -> int:
    password = _password()
    if password is None:
        return 1
    lookups = {"district_id": District, "institute_id": Institute, "employer_id": Employer}
    with SessionLocal() as db:
        for email, name, role, field, code in DEMO_ACCOUNTS:
            if db.scalar(select(AppUser.id).where(AppUser.email == email)) is not None:
                print(f"exists   {email}")
                continue
            scope: dict[str, object] = {}
            if field == "state_name":
                scope[field] = get_config().scope.state
            elif field is not None:
                model = lookups[field]
                record_id = db.scalar(select(model.id).where(model.code == code))
                if record_id is None:
                    print(f"skipped  {email}: no {model.__tablename__} {code}", file=sys.stderr)
                    continue
                scope[field] = record_id
            try:
                data = RegisterRequest(
                    email=email,
                    password=password,
                    display_name=name,
                    role=role,
                    consent=True,
                    **scope,
                )
                user = create_user(db, data, created_by=None, via="cli")
            except (AuthError, ValidationError) as exc:
                message = exc.message if isinstance(exc, AuthError) else str(exc)
                print(f"Could not create {email}: {message}", file=sys.stderr)
                return 1
            user.is_demo = True
            print(f"created  {email} ({role})")
        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
