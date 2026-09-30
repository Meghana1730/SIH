"""Create a user from the command line, e.g. the first admin:

    python -m app.cli.create_user --email admin@example.com --name "Platform Admin" --role admin

Scoped roles take our internal codes, e.g.:
    --role district_officer --district MH-NASHIK
    --role institute_admin  --institute <institute code>
    --role employer         --employer <employer code>
    --role state_officer    --state Maharashtra

The password is asked twice and is never shown or passed on the command line.
"""

import argparse
import getpass
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Candidate, District, Employer, Institute
from app.models.enums import Language, UserRole
from app.schemas.auth import RegisterRequest
from app.services.auth import AuthError, create_user


def _lookup(db: Session, model, column, value: str | None, label: str):
    if value is None:
        return None
    record_id = db.scalar(select(model.id).where(column == value))
    if record_id is None:
        raise LookupError(f"No {label} with code '{value}'.")
    return record_id


def main(
    argv: list[str] | None = None,
    ask_password: Callable[[str], str] = getpass.getpass,
    open_session: Callable[[], AbstractContextManager[Session]] = SessionLocal,
) -> int:
    parser = argparse.ArgumentParser(description="Create a KaushalSetu user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True, help="display name")
    parser.add_argument("--role", required=True, choices=[r.value for r in UserRole])
    parser.add_argument("--language", default="en", choices=[lang.value for lang in Language])
    parser.add_argument("--state", help="state_officer: state name")
    parser.add_argument("--district", help="district_officer: district code, e.g. MH-NASHIK")
    parser.add_argument("--institute", help="institute_admin: institute code")
    parser.add_argument("--employer", help="employer: employer code")
    parser.add_argument("--candidate", help="candidate: candidate pseudonym (optional)")
    args = parser.parse_args(argv)

    password = ask_password("Password: ")
    if password != ask_password("Repeat password: "):
        print("Passwords do not match. Nothing was created.", file=sys.stderr)
        return 1

    with open_session() as db:
        try:
            data = RegisterRequest(
                email=args.email,
                password=password,
                display_name=args.name,
                role=args.role,
                language=args.language,
                consent=True,
                state_name=args.state,
                district_id=_lookup(db, District, District.code, args.district, "district"),
                institute_id=_lookup(db, Institute, Institute.code, args.institute, "institute"),
                employer_id=_lookup(db, Employer, Employer.code, args.employer, "employer"),
                candidate_id=_lookup(
                    db, Candidate, Candidate.pseudonym, args.candidate, "candidate"
                ),
            )
            user = create_user(db, data, created_by=None, via="cli")
            db.commit()
        except (LookupError, AuthError, ValidationError) as exc:
            message = exc.message if isinstance(exc, AuthError) else str(exc)
            print(f"Could not create the user: {message}", file=sys.stderr)
            return 1
        print(f"Created {user.role} account {user.email} (id {user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
