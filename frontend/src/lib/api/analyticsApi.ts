// Demand, supply and mismatch from the analytics engine (GET /api/v1/analytics/*).
// Offline, the same shapes come from the demo snapshot (src/lib/demo/snapshot.json).

import { apiFetch, withFallbackAsync, type Sourced } from '@/lib/api/client'
import type {
  AnalyticsFilters,
  DistrictMismatch,
  Page,
  RoleDemand,
  RoleMismatch,
  RoleSupply,
  SkillDemand,
  SupplyBreakdown,
  SupplyGroup,
} from '@/lib/api/types'
import { loadSnapshot, type Snapshot } from '@/lib/demo/snapshot'

export type RunResult = {
  pipeline_run_id: string
  quarter: string
  demand_rows: number
  skill_rows: number
  supply_rows: number
  mismatch_rows: number
}

export type RoleHistoryPoint = {
  district: string
  role: string
  quarter: string
  score: number
  postings: number | null
}

export type SkillHistoryPoint = {
  district: string
  skill: string
  quarter: string
  score: number
  mentions: number
}

export function toQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value && value !== 'ALL') search.set(key, value)
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

type Filterable = {
  district: { code: string } | string
  role?: { code: string; sector: string }
  skill?: { code: string }
}

function matches(item: Filterable, filters: AnalyticsFilters): boolean {
  const district = typeof item.district === 'string' ? item.district : item.district.code
  if (filters.district && filters.district !== 'ALL' && district !== filters.district) return false
  if (item.role) {
    if (filters.sector && filters.sector !== 'ALL' && item.role.sector !== filters.sector) {
      return false
    }
    if (filters.role && item.role.code !== filters.role) return false
  }
  if (item.skill && filters.skill && item.skill.code !== filters.skill) return false
  return true
}

async function snapshotPage<T>(pick: (s: Snapshot) => T[]): Promise<Page<T>> {
  const snapshot = await loadSnapshot()
  const items = pick(snapshot)
  return {
    pipeline_run_id: snapshot.pipeline_run_id,
    computed_at: snapshot.computed_at,
    quarter: snapshot.quarter,
    count: items.length,
    items,
  }
}

async function quarters(): Promise<string[]> {
  return (await loadSnapshot()).quarters
}

export const analyticsApi = {
  roleDemand: (filters: AnalyticsFilters = {}): Promise<Sourced<Page<RoleDemand>>> =>
    withFallbackAsync(
      () =>
        apiFetch<Page<RoleDemand>>(
          `/api/v1/analytics/demand${toQuery({ ...filters, skill: undefined })}`,
        ),
      () => snapshotPage((s) => s.role_demand.filter((d) => matches(d, filters))),
    ),

  skillDemand: (filters: AnalyticsFilters = {}): Promise<Sourced<Page<SkillDemand>>> =>
    withFallbackAsync(
      () =>
        apiFetch<Page<SkillDemand>>(
          `/api/v1/analytics/demand${toQuery({
            district: filters.district,
            skill: filters.skill,
            quarter: filters.quarter,
            level: 'skill',
          })}`,
        ),
      () => snapshotPage((s) => s.skill_demand.filter((d) => matches(d, filters))),
    ),

  roleSupply: (filters: AnalyticsFilters = {}): Promise<Sourced<Page<RoleSupply>>> =>
    withFallbackAsync(
      () =>
        apiFetch<Page<RoleSupply>>(
          `/api/v1/analytics/supply${toQuery({
            district: filters.district,
            sector: filters.sector,
            role: filters.role,
          })}`,
        ),
      () => snapshotPage((s) => s.supply_role.filter((d) => matches(d, filters))),
    ),

  supplyBreakdown: (
    groupBy: Exclude<SupplyGroup, 'role'>,
    filters: AnalyticsFilters = {},
  ): Promise<Sourced<Page<SupplyBreakdown>>> =>
    withFallbackAsync(
      () =>
        apiFetch<Page<SupplyBreakdown>>(
          `/api/v1/analytics/supply${toQuery({
            district: filters.district,
            sector: filters.sector,
            group_by: groupBy,
          })}`,
        ),
      () =>
        snapshotPage((s) =>
          groupBy === 'course' ? s.supply_course.filter((d) => matches(d, filters)) : [],
        ),
    ),

  mismatch: (filters: AnalyticsFilters = {}): Promise<Sourced<Page<RoleMismatch>>> =>
    withFallbackAsync(
      () =>
        apiFetch<Page<RoleMismatch>>(
          `/api/v1/analytics/mismatch${toQuery({ ...filters, skill: undefined })}`,
        ),
      () => snapshotPage((s) => s.mismatch.filter((d) => matches(d, filters))),
    ),

  districtMismatch: (district: string, quarter?: string): Promise<Sourced<DistrictMismatch>> =>
    withFallbackAsync(
      () =>
        apiFetch<DistrictMismatch>(
          `/api/v1/analytics/districts/${encodeURIComponent(district)}/mismatch${toQuery({ quarter })}`,
        ),
      async () => {
        const snapshot = await loadSnapshot()
        const summary = snapshot.district_mismatch[district]
        if (!summary) throw new Error(`No demo data for district ${district}.`)
        const roles = snapshot.mismatch
          .filter((m) => m.district.code === district)
          .map((m) => ({
            ...m,
            abs_log_ratio:
              m.ratio === null
                ? undefined
                : Math.abs(Math.log(Math.max(m.ratio, summary.ratio_floor))),
          }))
          .sort((a, b) => (b.abs_log_ratio ?? 0) - (a.abs_log_ratio ?? 0))
        return { ...summary, roles }
      },
    ),

  /** Demand score per quarter for every role (charts). Live: one request per quarter. */
  roleHistory: (district?: string): Promise<Sourced<RoleHistoryPoint[]>> =>
    withFallbackAsync(
      async () => {
        const pages = await Promise.all(
          (await quarters()).map((quarter) =>
            apiFetch<Page<RoleDemand>>(`/api/v1/analytics/demand${toQuery({ district, quarter })}`),
          ),
        )
        return pages.flatMap((page) =>
          page.items.map((item) => ({
            district: item.district.code,
            role: item.role.code,
            quarter: item.quarter,
            score: item.demand_score,
            postings:
              (item.components.find((c) => c.name === 'postings')?.observed
                ?.postings_this_quarter as number | undefined) ?? null,
          })),
        )
      },
      async () =>
        (await loadSnapshot()).role_history.filter((h) => !district || h.district === district),
    ),

  /** Skill demand score and job-ad mentions per quarter (charts). */
  skillHistory: (
    filters: { district?: string; skill?: string } = {},
  ): Promise<Sourced<SkillHistoryPoint[]>> =>
    withFallbackAsync(
      async () => {
        const pages = await Promise.all(
          (await quarters()).map((quarter) =>
            apiFetch<Page<SkillDemand>>(
              `/api/v1/analytics/demand${toQuery({ ...filters, quarter, level: 'skill' })}`,
            ),
          ),
        )
        return pages.flatMap((page) =>
          page.items.map((item) => ({
            district: item.district.code,
            skill: item.skill.code,
            quarter: item.quarter,
            score: item.demand_score,
            mentions: item.mention_count,
          })),
        )
      },
      async () =>
        (await loadSnapshot()).skill_history.filter(
          (h) =>
            (!filters.district || filters.district === 'ALL' || h.district === filters.district) &&
            (!filters.skill || h.skill === filters.skill),
        ),
    ),

  quarters,

  /** Recompute demand, supply and mismatch (admin only). */
  run: () => apiFetch<RunResult>('/api/v1/analytics/run', { method: 'POST' }),
}
