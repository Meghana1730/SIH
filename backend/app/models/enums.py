"""Allowed values for "status-like" text columns.

We store these as plain text columns protected by CHECK constraints (not PostgreSQL ENUM
types), because adding a value later is then a one-line change in a migration.
Use the ``.value`` (e.g. ``SkillType.TECHNICAL.value``) or the member itself when writing.
"""

from enum import StrEnum


class Language(StrEnum):
    EN = "en"
    HI = "hi"
    MR = "mr"


# ---------- taxonomy ----------
class SkillType(StrEnum):
    TECHNICAL = "TECHNICAL"
    TOOL = "TOOL"
    SAFETY = "SAFETY"
    DOMAIN = "DOMAIN"
    CORE = "CORE"


class EdgeType(StrEnum):
    PROMOTION = "PROMOTION"
    LATERAL = "LATERAL"


# ---------- training ----------
class InstituteType(StrEnum):
    ITI = "ITI"
    PMKVY_TC = "PMKVY_TC"
    POLYTECHNIC = "POLYTECHNIC"
    OTHER = "OTHER"


class Ownership(StrEnum):
    GOVERNMENT = "GOVERNMENT"
    PRIVATE = "PRIVATE"
    OTHER = "OTHER"


class CourseType(StrEnum):
    ITI_TRADE = "ITI_TRADE"
    SHORT_TERM = "SHORT_TERM"
    DIPLOMA = "DIPLOMA"
    ADD_ON = "ADD_ON"
    OTHER = "OTHER"


class MappingReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EquipmentCondition(StrEnum):
    WORKING = "WORKING"
    NEEDS_REPAIR = "NEEDS_REPAIR"
    NOT_WORKING = "NOT_WORKING"


# ---------- employers & industry ----------
class EmployerSize(StrEnum):
    MICRO = "MICRO"
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    UNKNOWN = "UNKNOWN"


class SurveyChannel(StrEnum):
    WEB = "WEB"
    TELEGRAM = "TELEGRAM"
    WHATSAPP = "WHATSAPP"
    PHONE = "PHONE"


class Willingness(StrEnum):
    YES = "YES"
    MAYBE = "MAYBE"
    NO = "NO"


class ParticipantType(StrEnum):
    EMPLOYER = "EMPLOYER"
    INSTRUCTOR = "INSTRUCTOR"
    ASSOCIATION = "ASSOCIATION"
    OFFICIAL = "OFFICIAL"
    OTHER = "OTHER"


class InsightType(StrEnum):
    SKILL_GAP = "SKILL_GAP"
    OUTDATED_TOPIC = "OUTDATED_TOPIC"
    EQUIPMENT_NEED = "EQUIPMENT_NEED"
    OTHER = "OTHER"


class SectorEventType(StrEnum):
    NEW_PLANT = "NEW_PLANT"
    EXPANSION = "EXPANSION"
    CLOSURE = "CLOSURE"
    POLICY = "POLICY"
    PROJECT = "PROJECT"
    OTHER = "OTHER"


class GeographyLevel(StrEnum):
    GLOBAL = "GLOBAL"
    NATIONAL = "NATIONAL"
    STATE = "STATE"
    DISTRICT = "DISTRICT"
    RTO = "RTO"


# ---------- demand ----------
class ExtractionMethod(StrEnum):
    EXACT = "EXACT"  # the skill/role name itself appears in the text
    ALIAS = "ALIAS"
    FUZZY = "FUZZY"
    EMBEDDING = "EMBEDDING"
    LLM = "LLM"
    HUMAN = "HUMAN"
    # Ground truth written by the synthetic data generator (it knows which skills it put
    # into each synthetic job ad). Never used for real data.
    GENERATED = "GENERATED"
    # Role chosen because the ad's skills fit its skill profile (no title evidence).
    SKILL_PROFILE = "SKILL_PROFILE"
    # Skill implied by the matched role's essential skills (INFERRED, always reviewed).
    ROLE_PROFILE = "ROLE_PROFILE"


class EvidenceKind(StrEnum):
    """How a posting -> skill/role link is known."""

    OBSERVED = "OBSERVED"  # found in the posting's own text (quoted as evidence)
    INFERRED = "INFERRED"  # not stated; implied (e.g. by the matched role); always reviewed
    SYNTHETIC = "SYNTHETIC"  # written by the synthetic data generator (ground truth)


class MatchDecision(StrEnum):
    ACCEPT = "accept"  # confident enough to use automatically
    REVIEW = "review"  # stored, but a human should confirm it


class Proficiency(StrEnum):
    """Proficiency an ad ASKS for (from its wording); never a certified level."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"


class ExtractionStatus(StrEnum):
    PENDING = "PENDING"
    DONE = "DONE"
    FAILED = "FAILED"


class SalaryPeriod(StrEnum):
    DAY = "DAY"
    MONTH = "MONTH"
    YEAR = "YEAR"


# ---------- candidates ----------
class EducationLevel(StrEnum):
    BELOW_CLASS_10 = "BELOW_CLASS_10"
    CLASS_10 = "CLASS_10"
    CLASS_12 = "CLASS_12"
    ITI = "ITI"
    DIPLOMA = "DIPLOMA"
    GRADUATE = "GRADUATE"
    OTHER = "OTHER"


class SkillVerification(StrEnum):
    SELF = "SELF"
    ASSESSMENT = "ASSESSMENT"
    CERTIFICATE = "CERTIFICATE"


class EnrollmentStatus(StrEnum):
    ENROLLED = "ENROLLED"
    COMPLETED = "COMPLETED"
    DROPPED = "DROPPED"


class PlacementType(StrEnum):
    WAGE = "WAGE"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    APPRENTICESHIP = "APPRENTICESHIP"


# ---------- intelligence ----------
class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TrendStatus(StrEnum):
    EMERGING = "EMERGING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"


class MismatchStatus(StrEnum):
    UNDERSUPPLIED = "UNDER_SUPPLIED"
    BALANCED = "BALANCED"
    OVERSUPPLIED = "OVER_SUPPLIED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CourseFlag(StrEnum):
    OUTDATED = "OUTDATED"
    AT_RISK = "AT_RISK"
    LOW_PLACEMENT = "LOW_PLACEMENT"
    OVERSUPPLIED = "OVER_SUPPLIED"
    UNDERSUPPLIED = "UNDER_SUPPLIED"


class RecommendationType(StrEnum):
    ADD_MODULE = "ADD_MODULE"
    UPDATE_MODULE = "UPDATE_MODULE"
    DEMOTE_MODULE = "DEMOTE_MODULE"
    EXPAND_SEATS = "EXPAND_SEATS"
    REDUCE_SEATS = "REDUCE_SEATS"
    NEW_COURSE = "NEW_COURSE"
    TRAINER_UPSKILL = "TRAINER_UPSKILL"
    EQUIPMENT = "EQUIPMENT"


class RecommendationStatus(StrEnum):
    DRAFT = "DRAFT"
    UNDER_VALIDATION = "UNDER_VALIDATION"
    VALIDATED = "VALIDATED"
    IN_PLAN = "IN_PLAN"
    IMPLEMENTED = "IMPLEMENTED"
    REJECTED = "REJECTED"


class Priority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DecisionOwner(StrEnum):
    DGT_PROCESS = "DGT_PROCESS"
    SSC = "SSC"
    STATE_BOARD = "STATE_BOARD"
    INSTITUTE = "INSTITUTE"
    DISTRICT_COMMITTEE = "DISTRICT_COMMITTEE"


# ---------- validation & plans ----------
class VoteChoice(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NOT_NEEDED = "NOT_NEEDED"


class PledgeType(StrEnum):
    APPRENTICE = "APPRENTICE"
    HIRE = "HIRE"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"


# ---------- system ----------
class UserRole(StrEnum):
    STATE_OFFICER = "state_officer"
    DISTRICT_OFFICER = "district_officer"
    INSTITUTE_ADMIN = "institute_admin"
    SSC_REVIEWER = "ssc_reviewer"
    EMPLOYER = "employer"
    CANDIDATE = "candidate"
    ADMIN = "admin"


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ReviewKind(StrEnum):
    SKILL_MAPPING = "SKILL_MAPPING"
    NEW_SKILL = "NEW_SKILL"
    PLACE_MAPPING = "PLACE_MAPPING"
    ROLE_MAPPING = "ROLE_MAPPING"
    SYLLABUS_MAPPING = "SYLLABUS_MAPPING"


class ReviewItemStatus(StrEnum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    REMAPPED = "REMAPPED"
