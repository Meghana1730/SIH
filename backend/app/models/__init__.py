"""SQLAlchemy ORM models.

Every model module is imported here so that `Base.metadata` knows all tables
(Alembic uses it to create migrations). Import models from this package:

    from app.models import Skill, District
"""

from app.models.base import EMBEDDING_DIM, Base
from app.models.candidates import (
    Candidate,
    CandidateSkill,
    EmployerRating,
    Enrollment,
    PlacementOutcome,
)
from app.models.demand import JobPosting, PostingRole, PostingSkill, TrendSignal
from app.models.employers import (
    Consultation,
    ConsultationInsight,
    Employer,
    EmployerSurveyResponse,
    SectorEvent,
    SectorIndicator,
)
from app.models.engagement import DistrictPlan, Pledge, ValidationVote
from app.models.geography import District
from app.models.intelligence import (
    CourseHealth,
    DemandScore,
    Forecast,
    Mismatch,
    Recommendation,
    SupplyEstimate,
)
from app.models.qualifications import Nos, NosSkill, QualificationPack
from app.models.system import (
    AppUser,
    AuditLog,
    IngestionRun,
    LlmCache,
    PipelineRun,
    ReviewItem,
    ScoringConfigVersion,
)
from app.models.taxonomy import JobRole, RoleEdge, RoleSkill, Sector, Skill, SkillAlias
from app.models.training import (
    Course,
    CourseModule,
    CourseOffering,
    CourseRole,
    Equipment,
    Institute,
    InstituteEquipment,
    ModuleSkill,
    SkillEquipment,
    Trainer,
    TrainerSkill,
)

__all__ = [
    "EMBEDDING_DIM",
    "AppUser",
    "AuditLog",
    "Base",
    "Candidate",
    "CandidateSkill",
    "Consultation",
    "ConsultationInsight",
    "Course",
    "CourseHealth",
    "CourseModule",
    "CourseOffering",
    "CourseRole",
    "DemandScore",
    "District",
    "DistrictPlan",
    "Employer",
    "EmployerRating",
    "EmployerSurveyResponse",
    "Enrollment",
    "Equipment",
    "Forecast",
    "IngestionRun",
    "Institute",
    "InstituteEquipment",
    "JobPosting",
    "JobRole",
    "LlmCache",
    "Mismatch",
    "ModuleSkill",
    "Nos",
    "NosSkill",
    "PipelineRun",
    "PlacementOutcome",
    "Pledge",
    "PostingRole",
    "PostingSkill",
    "QualificationPack",
    "Recommendation",
    "ReviewItem",
    "RoleEdge",
    "RoleSkill",
    "ScoringConfigVersion",
    "Sector",
    "SectorEvent",
    "SectorIndicator",
    "Skill",
    "SkillAlias",
    "SkillEquipment",
    "SupplyEstimate",
    "Trainer",
    "TrainerSkill",
    "TrendSignal",
    "ValidationVote",
]
