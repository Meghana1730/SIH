// Skills: demand per district from the analytics API, plus which demo courses teach each skill.

import { analyticsApi } from '@/lib/api/analyticsApi'
import type { Sourced } from '@/lib/api/client'
import type { SkillDemand, TrendStatus } from '@/lib/api/types'
import { CURRICULA, OFFERINGS, skillSector } from '@/lib/demo/catalog'

export type SkillRow = {
  code: string
  name: string
  sector: ReturnType<typeof skillSector>
  /** Highest demand score across the selected districts. */
  top_score: number
  top_district: string
  mentions: number
  trend: TrendStatus | null
  districts: SkillDemand[]
  is_synthetic: boolean
}

const TREND_RANK: Record<string, number> = {
  EMERGING: 4,
  GROWING: 3,
  STABLE: 2,
  DECLINING: 1,
  INSUFFICIENT_DATA: 0,
}

/** One row per skill, combining the per-district demand items. */
export function groupSkills(items: SkillDemand[]): SkillRow[] {
  const bySkill = new Map<string, SkillDemand[]>()
  for (const item of items) {
    bySkill.set(item.skill.code, [...(bySkill.get(item.skill.code) ?? []), item])
  }
  return [...bySkill.entries()]
    .map(([code, districts]) => {
      const sorted = [...districts].sort((a, b) => b.demand_score - a.demand_score)
      const trend = [...districts].sort(
        (a, b) => (TREND_RANK[b.trend_status ?? ''] ?? 0) - (TREND_RANK[a.trend_status ?? ''] ?? 0),
      )[0].trend_status
      return {
        code,
        name: sorted[0].skill.name,
        sector: skillSector(code),
        top_score: sorted[0].demand_score,
        top_district: sorted[0].district.name,
        mentions: districts.reduce((sum, d) => sum + d.mention_count, 0),
        trend,
        districts: sorted,
        is_synthetic: districts.some((d) => d.is_synthetic),
      }
    })
    .sort((a, b) => b.top_score - a.top_score)
}

/** Demo courses that teach a skill, with the band taught (1 basic .. 3 advanced). */
export function coursesTeaching(skill: string) {
  return OFFERINGS.flatMap((offering) => {
    const curriculum = CURRICULA[offering.course]
    const band = Math.max(
      0,
      ...curriculum.modules.flatMap((m) => m.skills.filter(([c]) => c === skill).map(([, b]) => b)),
    )
    return band
      ? [
          {
            id: offering.id,
            name: curriculum.name,
            institute: offering.institute.name,
            district: offering.district,
            band,
          },
        ]
      : []
  })
}

export const skillsApi = {
  list: async (
    filters: { district?: string; quarter?: string } = {},
  ): Promise<Sourced<SkillRow[]>> => {
    const result = await analyticsApi.skillDemand(filters)
    return { ...result, data: groupSkills(result.data.items) }
  },
  detail: (skill: string, quarter?: string) => analyticsApi.skillDemand({ skill, quarter }),
  history: (skill: string) => analyticsApi.skillHistory({ skill }),
}
