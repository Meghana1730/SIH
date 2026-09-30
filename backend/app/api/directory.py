"""Scoped read endpoints for districts, institutes, employers and candidates.

Each endpoint (1) allows only certain roles (require_roles) and (2) only returns records
inside the user's scope (app/services/access.py). Out-of-scope single records give 403.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DbSession, error, get_in_scope, require_roles
from app.models import AppUser, Candidate, District, Employer, Institute
from app.models.enums import UserRole as R
from app.schemas.directory import CandidateOut, DistrictOut, EmployerOut, InstituteOut
from app.services.access import (
    candidate_scope,
    district_scope,
    employer_scope,
    institute_scope,
)

router = APIRouter(tags=["directory"])

StaffUser = Annotated[
    AppUser,
    Depends(
        require_roles(
            R.ADMIN,
            R.STATE_OFFICER,
            R.DISTRICT_OFFICER,
            R.INSTITUTE_ADMIN,
            R.SSC_REVIEWER,
            R.EMPLOYER,
        )
    ),
]
InstituteReader = Annotated[
    AppUser,
    Depends(
        require_roles(
            R.ADMIN, R.STATE_OFFICER, R.DISTRICT_OFFICER, R.INSTITUTE_ADMIN, R.SSC_REVIEWER
        )
    ),
]
EmployerReader = Annotated[
    AppUser, Depends(require_roles(R.ADMIN, R.STATE_OFFICER, R.DISTRICT_OFFICER, R.EMPLOYER))
]
CandidateReader = Annotated[
    AppUser, Depends(require_roles(R.ADMIN, R.INSTITUTE_ADMIN, R.CANDIDATE))
]
CandidateUser = Annotated[AppUser, Depends(require_roles(R.CANDIDATE))]


@router.get("/districts", response_model=list[DistrictOut])
def list_districts(user: StaffUser, db: DbSession) -> list[District]:
    """Districts you may work with (all, your state, or your own district)."""
    return list(db.scalars(select(District).where(district_scope(user)).order_by(District.name)))


@router.get("/institutes", response_model=list[InstituteOut])
def list_institutes(user: InstituteReader, db: DbSession) -> list[Institute]:
    query = select(Institute).where(institute_scope(user)).order_by(Institute.name)
    return list(db.scalars(query))


@router.get("/institutes/{institute_id}", response_model=InstituteOut)
def get_institute(institute_id: uuid.UUID, user: InstituteReader, db: DbSession) -> Institute:
    return get_in_scope(db, user, Institute, institute_id, institute_scope(user))


@router.get("/employers/{employer_id}", response_model=EmployerOut)
def get_employer(employer_id: uuid.UUID, user: EmployerReader, db: DbSession) -> Employer:
    return get_in_scope(db, user, Employer, employer_id, employer_scope(user))


@router.get("/candidates/me", response_model=CandidateOut)
def my_candidate_profile(user: CandidateUser, db: DbSession) -> Candidate:
    """The logged-in candidate's own profile."""
    if user.candidate_id is None:
        raise error(404, "NO_PROFILE", "Your account is not linked to a candidate profile yet.")
    return get_in_scope(db, user, Candidate, user.candidate_id, candidate_scope(user))


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: uuid.UUID, user: CandidateReader, db: DbSession) -> Candidate:
    return get_in_scope(db, user, Candidate, candidate_id, candidate_scope(user))
