"""Models for config/scoring.yaml (weights and thresholds; docs/03-prd.md §7)."""

from collections.abc import Iterable
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.config.base import ConfigModel, Fraction, require_sum_to_one
from app.models.enums import Confidence

Positive = Annotated[float, Field(gt=0)]


# ---------------------------------------------------------------- demand
class DemandWeights(ConfigModel):
    postings: Fraction
    employer_survey: Fraction
    growth_events: Fraction
    absorption: Fraction

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> Self:
        require_sum_to_one(self.model_dump(), "demand weights")
        return self

    def renormalized(self, available: Iterable[str]) -> dict[str, float]:
        """Weights for only the signals that have data, scaled to add up to 1.0 again.

        Example: if there is no employer-survey data, each remaining weight is divided by
        the sum of the remaining weights (see tests/test_config.py for a worked example).
        """
        names = set(available)
        unknown = names - set(type(self).model_fields)
        if unknown:
            raise ValueError(f"unknown demand components: {sorted(unknown)}")
        weights = {name: value for name, value in self.model_dump().items() if name in names}
        total = sum(weights.values())
        if total <= 0:
            raise ValueError("no demand component with data has a positive weight")
        return {name: value / total for name, value in weights.items()}


class CoverageFactors(ConfigModel):
    formal_heavy: Annotated[float, Field(gt=0, le=1)]
    informal_heavy: Annotated[float, Field(gt=0, le=1)]


class OpeningsSettings(ConfigModel):
    coverage_factors: CoverageFactors
    informal_heavy_roles: list[Annotated[str, StringConstraints(min_length=1)]]
    window_quarters: Annotated[int, Field(ge=1, le=12)]

    def factor_for(self, role_code: str) -> tuple[float, str]:
        """(coverage factor, label) for a role: an ASSUMPTION, shown with every result."""
        if role_code in self.informal_heavy_roles:
            return self.coverage_factors.informal_heavy, "informal_heavy"
        return self.coverage_factors.formal_heavy, "formal_heavy"


class PostingSignal(ConfigModel):
    volume_weight: Fraction
    growth_weight: Fraction
    growth_window_quarters: Annotated[int, Field(ge=2, le=12)]
    growth_min: float
    growth_max: float

    @model_validator(mode="after")
    def _valid(self) -> Self:
        require_sum_to_one(
            {"volume_weight": self.volume_weight, "growth_weight": self.growth_weight},
            "demand.posting_signal weights",
        )
        if not self.growth_min < self.growth_max:
            raise ValueError("demand.posting_signal.growth_min must be below growth_max")
        if self.growth_window_quarters % 2:
            raise ValueError("growth_window_quarters must be even (two equal halves)")
        return self


class SurveySignal(ConfigModel):
    half_life_quarters: Positive


class GrowthEventSignal(ConfigModel):
    lookahead_quarters: Annotated[int, Field(ge=1, le=12)]


class DemandConfig(ConfigModel):
    weights: DemandWeights
    missing_components: Literal["renormalize"]
    normalization: Literal["min_max", "percentile"]
    survey_lookback_months: Annotated[int, Field(ge=1, le=36)]
    posting_signal: PostingSignal
    survey: SurveySignal
    growth_events: GrowthEventSignal
    openings: OpeningsSettings


# ---------------------------------------------------------------- supply & mismatch
class SupplyConfig(ConfigModel):
    default_completion_rate: Annotated[float, Field(gt=0, le=1)]


class MismatchConfig(ConfigModel):
    undersupplied_below: Positive
    oversupplied_above: Positive
    district_ratio_floor: Annotated[float, Field(gt=0, lt=1)]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.undersupplied_below < self.oversupplied_above:
            raise ValueError(
                "undersupplied_below must be smaller than oversupplied_above "
                f"(got {self.undersupplied_below} and {self.oversupplied_above})"
            )
        return self


# ---------------------------------------------------------------- trends
class ExternalTrendRoute(ConfigModel):
    enabled: bool
    require_verified_source: bool
    min_signal_value: float | None

    @model_validator(mode="after")
    def _threshold_when_enabled(self) -> Self:
        if self.enabled and self.min_signal_value is None:
            raise ValueError(
                "external_trend is enabled but min_signal_value is null: agree what counts "
                "as a 'strong' external trend before enabling this route"
            )
        return self


class EmergingRule(ConfigModel):
    min_relative_growth: Positive
    min_mentions: Annotated[int, Field(ge=1)]
    external_trend: ExternalTrendRoute


class DecliningRule(ConfigModel):
    consecutive_quarter_drops: Annotated[int, Field(ge=1)]
    min_relative_decline: Annotated[float, Field(gt=0, le=1)]


class TrendConfig(ConfigModel):
    window_quarters: Annotated[int, Field(ge=2, le=12)]
    emerging: EmergingRule
    declining: DecliningRule

    @model_validator(mode="after")
    def _drops_fit_window(self) -> Self:
        # N drops in a row need N + 1 quarters of data.
        if self.declining.consecutive_quarter_drops > self.window_quarters - 1:
            raise ValueError(
                f"declining.consecutive_quarter_drops ({self.declining.consecutive_quarter_drops})"
                f" needs at least {self.declining.consecutive_quarter_drops + 1} quarters, "
                f"but window_quarters is {self.window_quarters}"
            )
        return self


# ---------------------------------------------------------------- course health
class HealthWeights(ConfigModel):
    placement_rate: Fraction
    work_relevance: Fraction
    recency: Fraction
    demand_trend: Fraction
    skill_coverage: Fraction

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> Self:
        require_sum_to_one(self.model_dump(), "course_health weights")
        return self


class CoverageSettings(ConfigModel):
    partial_credit: Fraction
    emerging_skill_importance_multiplier: Annotated[float, Field(ge=1)]


class OversupplyPenalty(ConfigModel):
    max_points: Annotated[float, Field(ge=0, le=100)]
    full_penalty_at_ratio: Positive


class HealthFlags(ConfigModel):
    outdated_coverage_below: Fraction
    at_risk_score_below: Annotated[float, Field(ge=0, le=100)]
    low_placement_rate_below: Fraction


class CourseHealthConfig(ConfigModel):
    weights: HealthWeights
    placement_lookback_cohorts: Annotated[int, Field(ge=1)]
    coverage: CoverageSettings
    oversupply_penalty: OversupplyPenalty
    flags: HealthFlags


# ---------------------------------------------------------------- forecast & events
class ForecastConfig(ConfigModel):
    method: Literal["linear_trend"]
    history_quarters: Annotated[int, Field(ge=2, le=40)]
    horizon_quarters: Annotated[int, Field(ge=1, le=12)]  # database column allows 1-12
    interval_fraction: Annotated[float, Field(gt=0, lt=1)]


class EventImpactConfig(ConfigModel):
    default_realization_factor: Fraction
    lag_start_quarter: Annotated[int, Field(ge=0, le=20)]
    lag_end_quarter: Annotated[int, Field(ge=0, le=20)]
    distribution: Literal["even"]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.lag_start_quarter > self.lag_end_quarter:
            raise ValueError("lag_start_quarter must not be after lag_end_quarter")
        return self


# ---------------------------------------------------------------- recommendations
class ValidationRule(ConfigModel):
    min_approvals: Annotated[int, Field(ge=1)]
    approvals_must_exceed_rejections: bool


class AddModuleRule(ConfigModel):
    min_skill_importance: Fraction


class DemoteModuleRule(ConfigModel):
    min_declining_weight_share: Fraction
    min_not_needed_votes: Annotated[int, Field(ge=1)]


class PriorityRule(ConfigModel):
    high_requires_min_confidence: Confidence


class RecommendationConfig(ConfigModel):
    # The database refuses recommendations with fewer than 2 evidence items unless they are
    # marked "limited evidence", so the configured minimum can be raised but not lowered.
    min_evidence_items: Annotated[int, Field(ge=2)]
    validation: ValidationRule
    add_module: AddModuleRule
    demote_module: DemoteModuleRule
    priority: PriorityRule


# ---------------------------------------------------------------- confidence
class ConfidenceLevelRule(ConfigModel):
    min_source_types: Annotated[int, Field(ge=1)]
    min_records: Annotated[int, Field(ge=1)]
    combine: Literal["all", "any"]


class ConfidenceConfig(ConfigModel):
    high: ConfidenceLevelRule
    medium: ConfidenceLevelRule

    @model_validator(mode="after")
    def _high_is_stricter(self) -> Self:
        if (
            self.high.min_source_types < self.medium.min_source_types
            or self.high.min_records < self.medium.min_records
        ):
            raise ValueError("confidence.high must be at least as strict as confidence.medium")
        return self


# ---------------------------------------------------------------- candidate guidance
class RankingWeights(ConfigModel):
    local_placement_rate: Fraction
    demand_trend: Fraction
    interest_match: Fraction
    proximity: Fraction

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> Self:
        require_sum_to_one(self.model_dump(), "candidate_guidance ranking_weights")
        return self


class ProximityScores(ConfigModel):
    same_district: Fraction
    other_district: Fraction

    @model_validator(mode="after")
    def _same_district_scores_higher(self) -> Self:
        if self.same_district < self.other_district:
            raise ValueError("proximity_scores.same_district must be >= other_district")
        return self


class CandidateGuidanceConfig(ConfigModel):
    top_n: Annotated[int, Field(ge=1, le=10)]
    ranking_weights: RankingWeights
    proximity_scores: ProximityScores


# ---------------------------------------------------------------- skill matching
class FuzzyMatching(ConfigModel):
    min_score: Fraction  # spelling similarity (0-1) needed to accept a fuzzy match
    min_input_length: Annotated[int, Field(ge=1, le=20)]


class EmbeddingMatching(ConfigModel):
    top_k: Annotated[int, Field(ge=1, le=50)]


class SkillMatchingConfig(ConfigModel):
    auto_accept_confidence: Fraction
    min_confidence: Fraction
    default_band: Annotated[int, Field(ge=1, le=4)]
    alias_confidence: Fraction
    fuzzy: FuzzyMatching
    embedding: EmbeddingMatching
    llm_fallback_max_confidence: Fraction

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.min_confidence < self.auto_accept_confidence:
            raise ValueError("min_confidence must be smaller than auto_accept_confidence")
        if self.llm_fallback_max_confidence >= self.auto_accept_confidence:
            raise ValueError(
                "llm_fallback_max_confidence must be below auto_accept_confidence, so an LLM "
                "answer is always checked by a human"
            )
        return self


# ---------------------------------------------------------------- job pipeline
class InferredSkills(ConfigModel):
    enabled: bool
    min_role_confidence: Fraction  # only from roles matched at least this confidently
    min_importance: Fraction  # only the role's essential skills
    confidence_factor: Fraction  # inferred confidence = role conf x importance x factor


class ProficiencyBands(ConfigModel):
    basic: Annotated[int, Field(ge=1, le=4)]
    intermediate: Annotated[int, Field(ge=1, le=4)]
    advanced: Annotated[int, Field(ge=1, le=4)]


class JobExtractionConfig(ConfigModel):
    fuzzy_extra_words: Annotated[int, Field(ge=0, le=3)]
    fuzzy_min_single_word_chars: Annotated[int, Field(ge=1, le=30)]
    max_phrase_words: Annotated[int, Field(ge=1, le=20)]
    max_phrases_per_posting: Annotated[int, Field(ge=1, le=500)]
    llm_min_candidate_score: Fraction
    llm_phrase_extraction_min_words: Annotated[int, Field(ge=1)]
    inferred_skills: InferredSkills
    proficiency_bands: ProficiencyBands


class TitleConfidence(ConfigModel):
    exact: Fraction  # the title IS a role title
    alias: Fraction  # the title IS a role alias
    contained: Fraction  # the title contains a role title/alias
    description: Fraction  # only the description mentions a role title/alias


class RoleMatchingConfig(ConfigModel):
    auto_accept_confidence: Fraction
    min_confidence: Fraction
    title_confidence: TitleConfidence
    fuzzy_min_score: Fraction
    skill_agreement_bonus: Fraction
    skills_only_factor: Fraction
    ambiguity_margin: Fraction
    sector_mismatch_factor: Fraction

    @model_validator(mode="after")
    def _skills_alone_need_review(self) -> Self:
        if not self.min_confidence < self.auto_accept_confidence:
            raise ValueError("min_confidence must be smaller than auto_accept_confidence")
        if self.skills_only_factor >= self.auto_accept_confidence:
            raise ValueError(
                "skills_only_factor must be below auto_accept_confidence, so a role guessed "
                "from skills alone is always checked by a human"
            )
        return self


# ---------------------------------------------------------------- whole file
class ScoringConfig(ConfigModel):
    # Stored in scoring_config_version.version (max 32 characters).
    version: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._-]{1,32}$")]
    demand: DemandConfig
    supply: SupplyConfig
    mismatch: MismatchConfig
    trend: TrendConfig
    course_health: CourseHealthConfig
    forecast: ForecastConfig
    event_impact: EventImpactConfig
    recommendations: RecommendationConfig
    confidence: ConfidenceConfig
    candidate_guidance: CandidateGuidanceConfig
    skill_matching: SkillMatchingConfig
    job_extraction: JobExtractionConfig
    role_matching: RoleMatchingConfig

    @model_validator(mode="after")
    def _penalty_starts_after_oversupply(self) -> Self:
        full_at = self.course_health.oversupply_penalty.full_penalty_at_ratio
        if full_at <= self.mismatch.oversupplied_above:
            raise ValueError(
                "course_health.oversupply_penalty.full_penalty_at_ratio "
                f"({full_at}) must be greater than mismatch.oversupplied_above "
                f"({self.mismatch.oversupplied_above})"
            )
        return self
