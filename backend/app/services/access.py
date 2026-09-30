"""Who may see which records ("scope"). The single source of truth for data-level access.

Each function returns a SQL condition for one table, based on the logged-in user. Endpoints
add it to their queries, so out-of-scope rows are never even loaded:

    select(Institute).where(institute_scope(user))

Rows a user may see (admin sees everything):

    district  : state_officer own state | district_officer own district | ssc_reviewer all
                institute_admin / employer: the district of their institute / employer
    institute : state_officer own state | district_officer own district | ssc_reviewer all
                institute_admin own institute
    employer  : state_officer own state | district_officer own district | employer itself
    candidate : candidate itself | institute_admin candidates enrolled at own institute
                (officers work with aggregated numbers, never individual candidates)

Anything not listed is "none".
Which ROLES may call an endpoint at all is declared on the endpoint with require_roles().
"""

from sqlalchemy import ColumnElement, false, select, true

from app.models import AppUser, Candidate, CourseOffering, District, Employer, Enrollment, Institute
from app.models.enums import UserRole as R


def _state_district_ids(user: AppUser):
    return select(District.id).where(District.state_name == user.state_name)


def district_scope(user: AppUser) -> ColumnElement[bool]:
    match user.role:
        case R.ADMIN | R.SSC_REVIEWER:
            return true()
        case R.STATE_OFFICER:
            return District.state_name == user.state_name
        case R.DISTRICT_OFFICER:
            return District.id == user.district_id
        case R.INSTITUTE_ADMIN:
            own = select(Institute.district_id).where(Institute.id == user.institute_id)
            return District.id == own.scalar_subquery()
        case R.EMPLOYER:
            own = select(Employer.district_id).where(Employer.id == user.employer_id)
            return District.id == own.scalar_subquery()
        case _:
            return false()


def institute_scope(user: AppUser) -> ColumnElement[bool]:
    match user.role:
        case R.ADMIN | R.SSC_REVIEWER:
            return true()
        case R.STATE_OFFICER:
            return Institute.district_id.in_(_state_district_ids(user))
        case R.DISTRICT_OFFICER:
            return Institute.district_id == user.district_id
        case R.INSTITUTE_ADMIN:
            return Institute.id == user.institute_id
        case _:
            return false()


def employer_scope(user: AppUser) -> ColumnElement[bool]:
    match user.role:
        case R.ADMIN:
            return true()
        case R.STATE_OFFICER:
            return Employer.district_id.in_(_state_district_ids(user))
        case R.DISTRICT_OFFICER:
            return Employer.district_id == user.district_id
        case R.EMPLOYER:
            return Employer.id == user.employer_id
        case _:
            return false()


def candidate_scope(user: AppUser) -> ColumnElement[bool]:
    match user.role:
        case R.ADMIN:
            return true()
        case R.CANDIDATE if user.candidate_id is not None:
            return Candidate.id == user.candidate_id
        case R.INSTITUTE_ADMIN:
            enrolled_here = (
                select(Enrollment.candidate_id)
                .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
                .where(CourseOffering.institute_id == user.institute_id)
            )
            return Candidate.id.in_(enrolled_here)
        case _:
            return false()
