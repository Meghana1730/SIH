// Response types. Analytics/auth/directory types mirror the FastAPI backend
// (backend/app/analytics/queries.py, app/schemas/*.py). Types for features without a backend
// endpoint yet (courses, recommendations, employer, candidate, plans) are frontend-defined and
// served from src/lib/demo.

export type Confidence = 'HIGH' | 'MEDIUM' | 'LOW'
export type MismatchStatus = 'UNDER_SUPPLIED' | 'BALANCED' | 'OVER_SUPPLIED' | 'INSUFFICIENT_DATA'
export type TrendStatus = 'EMERGING' | 'GROWING' | 'STABLE' | 'DECLINING' | 'INSUFFICIENT_DATA'
export type SectorCode = 'ELECTRICAL' | 'EV' | 'SOLAR_PV'

export type UserRole =
  | 'admin'
  | 'state_officer'
  | 'district_officer'
  | 'ssc_reviewer'
  | 'institute_admin'
  | 'employer'
  | 'candidate'

export type User = {
  id: string
  email: string
  display_name: string
  role: UserRole
  language: 'en' | 'hi' | 'mr'
  state_name: string | null
  district_id: string | null
  institute_id: string | null
  employer_id: string | null
  candidate_id: string | null
  is_active: boolean
  is_demo: boolean
  last_login_at: string | null
  created_at: string
}

export type TokenResponse = {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

export type District = { id: string; code: string; name: string; state_name: string }
export type Institute = {
  id: string
  code: string
  name: string
  institute_type: string
  district_id: string
  is_synthetic: boolean
}

export type AuditEntry = {
  id: string
  created_at: string
  action: string
  user_id: string | null
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown>
}

export type ApiHealth = {
  status: string
  service: string
  version: string
  env: string
  scoring_config_version: string
  scoring_config_sha256: string
}

export type DbHealth = {
  status: string
  database: string
  pgvector: { installed: boolean; version: string | null }
}

// ---------------------------------------------------------------- analytics explanations
export type Reason = {
  code: string
  text: string
  type: 'reason'
  evidence: Record<string, unknown>
  is_synthetic: boolean
}

export type Assumption = {
  name: string
  type: 'assumption'
  value: unknown
  source: string
  note?: string
  kind?: string
  effective?: Record<string, number>
}

export type Explanation = {
  observed_inputs: Record<string, unknown>
  estimated_values: Record<string, number | null>
  assumptions: Assumption[]
  confidence: Confidence
  reasons: Reason[]
  is_synthetic: boolean
  synthetic_share: number
  data_label: string
}

export type DemandComponent = {
  name: 'postings' | 'employer_survey' | 'growth_events' | 'absorption' | string
  value: number | null
  weight: number
  effective_weight: number
  available: boolean
  records: number
  synthetic_records: number
  observed: Record<string, unknown>
  note?: string
}

export type DistrictRef = { code: string; name: string }
export type RoleRef = { code: string; title: string; sector: SectorCode }
export type SkillRef = { code: string; name: string }

export type RoleDemand = Explanation & {
  district: DistrictRef
  quarter: string
  role: RoleRef
  demand_score: number
  components: DemandComponent[]
}

export type SkillDemand = Explanation & {
  district: DistrictRef
  quarter: string
  skill: SkillRef
  trend_status: TrendStatus | null
  mention_count: number
  demand_score: number
  components: DemandComponent[]
}

export type Page<T> = {
  pipeline_run_id: string
  computed_at: string | null
  quarter: string | null
  count: number
  items: T[]
}

export type Offering = {
  offering_id: string
  institute: string
  institute_name: string
  course: string
  course_name: string
  academic_year: string
  seats: number
  seats_filled: number | null
  completion_rate: number | null
  completion_rate_is_default: boolean
  trained_output: number
  is_synthetic: boolean
}

export type RoleSupply = Explanation & {
  district: DistrictRef
  role: RoleRef
  academic_year: string
  trained_output_per_year: number
  formula: string
  offerings: Offering[]
}

export type SupplyGroup = 'district' | 'institute' | 'course' | 'role' | 'skill'

export type SupplyBreakdown = {
  district: string
  group_by: SupplyGroup
  key: string
  label: string
  academic_year: string
  trained_output: number
  offerings: Offering[]
  default_completion_used: boolean
  is_synthetic: boolean
  synthetic_share: number
  assumptions: Assumption[]
}

export type RoleMismatch = Explanation & {
  district: DistrictRef
  role: RoleRef
  quarter: string
  demand_score: number | null
  supply: number
  estimated_openings: number
  ratio: number | null
  status: MismatchStatus
  abs_log_ratio?: number
}

export type DistrictMismatch = {
  pipeline_run_id: string
  district: DistrictRef
  quarter: string
  mismatch_score: number | null
  definition: string
  ratio_floor: number
  status_counts: Partial<Record<MismatchStatus, number>>
  is_synthetic: boolean
  synthetic_share: number
  data_label: string
  roles: RoleMismatch[]
}

export type AnalyticsFilters = {
  district?: string
  sector?: string
  role?: string
  skill?: string
  quarter?: string
}

export type RunSummary = Record<string, unknown>

// ---------------------------------------------------------------- frontend-defined (demo)
export type Priority = 'HIGH' | 'MEDIUM' | 'LOW'
export type CourseHealthStatus = 'HEALTHY' | 'WATCH' | 'AT_RISK'

export type EvidenceItem = {
  label: string
  detail: string
  kind: 'OBSERVED' | 'INFERRED' | 'SYNTHETIC' | 'ASSUMPTION'
  source: string
}

export type CurriculumSkill = {
  skill: SkillRef
  /** 0 = not taught, 1 basic, 2 intermediate, 3 advanced */
  band_taught: number
  hours: number
  demand_score: number | null
  trend: TrendStatus | null
}

export type CourseHealthComponent = {
  name: string
  weight: number
  value: number
  note: string
}

export type Course = {
  id: string
  code: string
  name: string
  institute: { code: string; name: string }
  district: DistrictRef
  sector: SectorCode
  primary_role: RoleRef
  duration_hours: number
  seats: number
  seats_filled: number
  completion_rate: number
  placement_rate: number
  health_score: number
  health_status: CourseHealthStatus
  health_components: CourseHealthComponent[]
  curriculum: CurriculumSkill[]
  missing_skills: { skill: SkillRef; demand_score: number; trend: TrendStatus; postings: number }[]
  recommendation_ids: string[]
  is_synthetic: true
}

export type RecommendationAction =
  | 'ADD_MODULE'
  | 'UPDATE_MODULE'
  | 'REDUCE_SEATS'
  | 'INCREASE_SEATS'
  | 'RETIRE_MODULE'
  | 'START_COURSE'
  | 'EMPLOYER_PARTNERSHIP'

export type RecommendationStatus = 'NEW' | 'ACCEPTED' | 'IN_REVIEW' | 'DISMISSED'

export type Recommendation = {
  id: string
  action: RecommendationAction
  title: string
  target: string
  course_id: string | null
  district: DistrictRef
  sector: SectorCode
  priority_score: number
  priority: Priority
  reason: string
  expected_impact: string
  evidence: EvidenceItem[]
  confidence: Confidence
  status: RecommendationStatus
  employer_validations: number
  is_synthetic: true
}

export type Employer = {
  code: string
  name: string
  district: DistrictRef
  size: 'MICRO' | 'SMALL' | 'MEDIUM' | 'LARGE'
  sector: SectorCode
  is_synthetic: true
}

export type EmployerDemandSubmission = {
  employer_code: string
  role_code: string
  skills: string[]
  headcount: number
  horizon_months: number
  notes?: string
}

export type ApprenticeshipPledge = {
  employer_code: string
  course_id: string
  seats: number
  start_quarter: string
}

export type EmployerActivity = {
  id: string
  kind: 'DEMAND' | 'VALIDATION' | 'PLEDGE'
  text: string
  at: string
  is_synthetic: true
}

export type CareerPath = {
  role: RoleRef
  district: DistrictRef
  demand_score: number
  trend: TrendStatus
  estimated_openings: number
  typical_courses: { name: string; institute: string; duration: string }[]
  skills_to_learn: SkillRef[]
  why: string
  is_synthetic: true
}

export type PlanAction = {
  id: string
  title: string
  owner: string
  due: string
  status: 'PLANNED' | 'IN_PROGRESS' | 'DONE'
  linked_recommendation: string | null
}

export type DistrictPlan = {
  id: string
  district: DistrictRef
  title: string
  period: string
  status: 'DRAFT' | 'IN_REVIEW' | 'APPROVED'
  summary: string
  priorities: { title: string; detail: string; metric: string }[]
  actions: PlanAction[]
  commitments: { label: string; value: string }[]
  prepared_by: string
  updated_at: string
  is_synthetic: true
}

export type Notification = {
  id: string
  title: string
  body: string
  at: string
  href?: string
  tone: 'info' | 'warning' | 'danger' | 'success'
}
