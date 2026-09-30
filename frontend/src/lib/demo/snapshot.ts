// The offline demo dataset: a snapshot of the analytics API over the SYNTHETIC demo world
// (scripts/snapshot_demo.py). Loaded lazily so it is only downloaded when demo data is needed.

import type {
  District,
  DistrictMismatch,
  RoleDemand,
  RoleMismatch,
  RoleSupply,
  SkillDemand,
  SupplyBreakdown,
} from '@/lib/api/types'

export type Snapshot = {
  about: string
  pipeline_run_id: string
  computed_at: string
  quarter: string
  quarters: string[]
  districts: District[]
  role_demand: RoleDemand[]
  skill_demand: SkillDemand[]
  mismatch: RoleMismatch[]
  district_mismatch: Record<string, Omit<DistrictMismatch, 'roles'>>
  supply_course: SupplyBreakdown[]
  supply_role: RoleSupply[]
  role_history: {
    district: string
    role: string
    quarter: string
    score: number
    postings: number | null
  }[]
  skill_history: {
    district: string
    skill: string
    quarter: string
    score: number
    mentions: number
  }[]
}

let cached: Promise<Snapshot> | null = null

export function loadSnapshot(): Promise<Snapshot> {
  cached ??= import('./snapshot.json').then((m) => m.default as unknown as Snapshot)
  return cached
}
