// Candidate guidance. Career paths rank roles by the district's demand (live analytics API when
// reachable). The assistant is rule-based: it only restates the numbers on screen and never calls
// an AI model or invents figures.

import { analyticsApi } from '@/lib/api/analyticsApi'
import type { Sourced } from '@/lib/api/client'
import type { CareerPath, RoleDemand, SkillRef, TrendStatus } from '@/lib/api/types'
import { CURRICULA, OFFERINGS, SKILL_NAMES } from '@/lib/demo/catalog'

function trendOf(item: RoleDemand): TrendStatus {
  const postings = item.components.find((c) => c.name === 'postings')?.observed as
    | { recent_postings?: number; earlier_postings?: number }
    | undefined
  if (!postings?.recent_postings || postings.earlier_postings === undefined) return 'STABLE'
  const growth = (postings.recent_postings - postings.earlier_postings) / Math.max(1, postings.earlier_postings)
  if (growth >= 0.3) return 'GROWING'
  if (growth <= -0.2) return 'DECLINING'
  return 'STABLE'
}

function pathFor(item: RoleDemand): CareerPath {
  const courses = Object.entries(CURRICULA).filter(([, c]) => c.role.code === item.role.code)
  const skills = new Map<string, SkillRef>()
  for (const [, course] of courses) {
    for (const module of course.modules) {
      for (const [code] of module.skills) skills.set(code, { code, name: SKILL_NAMES[code] ?? code })
    }
  }
  const typical = courses.flatMap(([code, course]) => {
    const local = OFFERINGS.filter((o) => o.course === code && o.district.code === item.district.code)
    const where = local.length ? local : OFFERINGS.filter((o) => o.course === code).slice(0, 1)
    const hours = course.modules.reduce((sum, m) => sum + m.hours, 0)
    return where.map((o) => ({
      name: course.name,
      institute: o.institute.name,
      duration: hours >= 400 ? '2 years (ITI)' : `${hours} hours`,
    }))
  })
  const reason = item.reasons[0]?.text
  return {
    role: item.role,
    district: item.district,
    demand_score: item.demand_score,
    trend: trendOf(item),
    estimated_openings: Number(item.estimated_values.estimated_annual_openings ?? 0),
    typical_courses: typical,
    skills_to_learn: [...skills.values()].slice(0, 6),
    why: reason ?? `Demand score ${item.demand_score.toFixed(0)}/100 in ${item.district.name}.`,
    is_synthetic: true,
  }
}

export const candidateApi = {
  careerPaths: async (district: string): Promise<Sourced<CareerPath[]>> => {
    const demand = await analyticsApi.roleDemand({ district })
    return {
      ...demand,
      data: demand.data.items
        .filter((item) => item.district.code === district)
        .sort((a, b) => b.demand_score - a.demand_score)
        .map(pathFor),
    }
  },

  /** Rule-based answers built only from the career paths shown to the candidate. */
  ask: (question: string, paths: CareerPath[]): string => {
    const q = question.toLowerCase()
    const top = paths[0]
    if (!top) return 'I have no demand data for this district yet.'
    const mentioned = paths.find(
      (p) => q.includes(p.role.title.toLowerCase()) || q.includes(p.role.code.replace(/-/g, ' ')),
    )
    if (mentioned) {
      const courses = mentioned.typical_courses.map((c) => `${c.name} at ${c.institute}`).join('; ')
      return `${mentioned.role.title} in ${mentioned.district.name}: demand ${mentioned.demand_score.toFixed(0)}/100, about ${Math.round(mentioned.estimated_openings)} estimated openings a year (a model estimate, not an official figure). ${courses ? `Courses: ${courses}.` : 'No demo course trains for it here yet.'}`
    }
    if (q.includes('ev') || q.includes('electric vehicle')) {
      const ev = paths.filter((p) => p.role.sector === 'EV')
      return ev.length
        ? `EV roles in ${top.district.name}: ${ev.map((p) => `${p.role.title} (${p.demand_score.toFixed(0)}/100)`).join(', ')}. Key skills: ${ev[0].skills_to_learn.map((s) => s.name).join(', ')}.`
        : 'No EV roles have demand data here.'
    }
    if (q.includes('solar')) {
      const solar = paths.filter((p) => p.role.sector === 'SOLAR_PV')
      return solar.length
        ? `Solar roles in ${top.district.name}: ${solar.map((p) => `${p.role.title} (${p.demand_score.toFixed(0)}/100)`).join(', ')}.`
        : 'No solar roles have demand data here.'
    }
    if (q.includes('course') || q.includes('train') || q.includes('study')) {
      return `For the highest-demand role here (${top.role.title}), look at: ${top.typical_courses.map((c) => `${c.name} at ${c.institute}`).join('; ') || 'no local demo course yet'}.`
    }
    if (q.includes('declin') || q.includes('avoid')) {
      const low = paths[paths.length - 1]
      return `The lowest demand here is for ${low.role.title} (${low.demand_score.toFixed(0)}/100).`
    }
    return `The highest demand in ${top.district.name} is for ${top.role.title} (${top.demand_score.toFixed(0)}/100). Ask me about a role, EV, solar, or courses.`
  },
}
