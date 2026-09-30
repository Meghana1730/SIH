// Course health = how well a course matches what its district's employers ask for.
// Computed in the frontend (the backend has no course-health endpoint yet) from:
//   * the course curriculum (catalog.ts, a copy of the synthetic spec)
//   * the district's skill demand (analytics API, or the demo snapshot offline)
//   * the course's completions and placements (synthetic)
//
//   health = 0.35 x demand alignment      top-6 demanded skills of the course's related sectors
//                                         taught (advanced/intermediate = 1, basic = 0.5)
//          + 0.25 x emerging coverage     the district's EMERGING skills in those sectors taught
//                                         (same scoring; 50 = neutral when there are none)
//          + 0.25 x placement rate        placed / completed
//          + 0.15 x curriculum freshness  share of hours NOT spent on DECLINING skills
//   HEALTHY >= 70, WATCH 50-69, AT_RISK < 50. A demo heuristic, not an official rating.

import type {
  Course,
  CourseHealthComponent,
  CourseHealthStatus,
  CurriculumSkill,
  SkillDemand,
} from '@/lib/api/types'
import {
  CURRICULA,
  OFFERINGS,
  SKILL_NAMES,
  skillSector,
  type OfferingRecord,
} from '@/lib/demo/catalog'
import { RECOMMENDATIONS } from '@/lib/demo/recommendations'

export const HEALTH_WEIGHTS = {
  alignment: 0.35,
  emerging: 0.25,
  placement: 0.25,
  freshness: 0.15,
} as const

const TOP_N = 6

export function healthStatus(score: number): CourseHealthStatus {
  if (score >= 70) return 'HEALTHY'
  if (score >= 50) return 'WATCH'
  return 'AT_RISK'
}

function credit(band: number): number {
  if (band >= 2) return 1
  if (band === 1) return 0.5
  return 0
}

export function buildCourse(offering: OfferingRecord, districtSkills: SkillDemand[]): Course {
  const curriculum = CURRICULA[offering.course]
  const bands = new Map<string, number>()
  const hours = new Map<string, number>()
  for (const module of curriculum.modules) {
    for (const [code, band] of module.skills) {
      bands.set(code, Math.max(band, bands.get(code) ?? 0))
      hours.set(code, (hours.get(code) ?? 0) + module.hours / module.skills.length)
    }
  }
  const demand = new Map(districtSkills.map((s) => [s.skill.code, s]))
  const ranked = districtSkills
    .filter((s) => curriculum.related.includes(skillSector(s.skill.code)))
    .sort((a, b) => b.demand_score - a.demand_score)
  const top = ranked.slice(0, TOP_N)
  const alignment = top.length
    ? (100 * top.reduce((sum, s) => sum + credit(bands.get(s.skill.code) ?? 0), 0)) / top.length
    : 50
  const emergingSkills = ranked.filter((s) => s.trend_status === 'EMERGING')
  const emerging = emergingSkills.length
    ? (100 * emergingSkills.reduce((sum, s) => sum + credit(bands.get(s.skill.code) ?? 0), 0)) /
      emergingSkills.length
    : 50
  const placement = offering.completed ? (100 * offering.placed) / offering.completed : 0
  const totalHours = curriculum.modules.reduce((sum, m) => sum + m.hours, 0)
  const decliningHours = curriculum.modules
    .filter((m) => m.skills.some(([code]) => demand.get(code)?.trend_status === 'DECLINING'))
    .reduce((sum, m) => sum + m.hours, 0)
  const freshness = totalHours ? (100 * (totalHours - decliningHours)) / totalHours : 100

  const taughtTop = top.filter((s) => credit(bands.get(s.skill.code) ?? 0) === 1).length
  const components: CourseHealthComponent[] = [
    {
      name: 'Demand alignment',
      weight: HEALTH_WEIGHTS.alignment,
      value: alignment,
      note: `${taughtTop} of the top ${top.length} demanded ${curriculum.related.map((r) => r.replace('_', ' ').toLowerCase()).join('/')} skills in ${offering.district.name} taught to intermediate or above`,
    },
    {
      name: 'Emerging-skill coverage',
      weight: HEALTH_WEIGHTS.emerging,
      value: emerging,
      note: emergingSkills.length
        ? `${emergingSkills.length} emerging related skills in ${offering.district.name}; covered: ${
            emergingSkills
              .filter((s) => (bands.get(s.skill.code) ?? 0) > 0)
              .map((s) => `${s.skill.name}${bands.get(s.skill.code) === 1 ? ' (basic only)' : ''}`)
              .join(', ') || 'none'
          }`
        : 'no emerging related skills in this district (neutral 50)',
    },
    {
      name: 'Placement rate',
      weight: HEALTH_WEIGHTS.placement,
      value: placement,
      note: `${offering.placed} of ${offering.completed} completers placed (2025-26)`,
    },
    {
      name: 'Curriculum freshness',
      weight: HEALTH_WEIGHTS.freshness,
      value: freshness,
      note: decliningHours
        ? `${decliningHours} of ${totalHours} hours spent on declining skills`
        : 'no hours on declining skills',
    },
  ]
  const score = Math.round(components.reduce((sum, c) => sum + c.weight * c.value, 0))

  const skillCodes = new Set([...bands.keys(), ...top.map((s) => s.skill.code)])
  const skills: CurriculumSkill[] = [...skillCodes]
    .map((code) => ({
      skill: { code, name: demand.get(code)?.skill.name ?? SKILL_NAMES[code] ?? code },
      band_taught: bands.get(code) ?? 0,
      hours: Math.round(hours.get(code) ?? 0),
      demand_score: demand.get(code)?.demand_score ?? null,
      trend: demand.get(code)?.trend_status ?? null,
    }))
    .sort((a, b) => (b.demand_score ?? -1) - (a.demand_score ?? -1))

  const missing = ranked
    .filter(
      (s) =>
        (bands.get(s.skill.code) ?? 0) < 2 &&
        (s.trend_status === 'EMERGING' || s.demand_score >= 60),
    )
    .map((s) => ({
      skill: s.skill,
      demand_score: s.demand_score,
      trend: s.trend_status ?? 'STABLE',
      postings: s.mention_count,
    }))

  return {
    id: offering.id,
    code: offering.course,
    name: curriculum.name,
    institute: offering.institute,
    district: offering.district,
    sector: curriculum.sector,
    primary_role: curriculum.role,
    duration_hours: totalHours,
    seats: offering.seats,
    seats_filled: offering.seats_filled,
    completion_rate: offering.seats_filled ? offering.completed / offering.seats_filled : 0,
    placement_rate: placement / 100,
    health_score: score,
    health_status: healthStatus(score),
    health_components: components,
    curriculum: skills,
    missing_skills: missing,
    recommendation_ids: RECOMMENDATIONS.filter((r) => r.course_id === offering.id).map((r) => r.id),
    is_synthetic: true,
  }
}

export function buildCourses(skillDemand: SkillDemand[]): Course[] {
  return OFFERINGS.map((offering) =>
    buildCourse(
      offering,
      skillDemand.filter((s) => s.district.code === offering.district.code),
    ),
  )
}
