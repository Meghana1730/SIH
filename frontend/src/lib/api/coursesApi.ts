// Course health. The backend has no course endpoint yet: the catalogue is demo data and the
// health score is computed in the browser (src/lib/demo/courseHealth.ts) from the district's
// skill demand, which comes from the live analytics API when it is reachable.

import { analyticsApi } from '@/lib/api/analyticsApi'
import type { Sourced } from '@/lib/api/client'
import type { Course } from '@/lib/api/types'
import { buildCourses } from '@/lib/demo/courseHealth'

function note(skillSource: 'live' | 'demo'): string {
  return skillSource === 'live'
    ? 'Course catalogue is demo data (no course API yet); health uses live skill demand from the analytics API.'
    : 'Course catalogue and skill demand are demo data.'
}

export const coursesApi = {
  list: async (): Promise<Sourced<Course[]>> => {
    const skills = await analyticsApi.skillDemand()
    return { data: buildCourses(skills.data.items), source: 'demo', note: note(skills.source) }
  },
  get: async (id: string): Promise<Sourced<Course | null>> => {
    const all = await coursesApi.list()
    return { ...all, data: all.data.find((c) => c.id === id) ?? null }
  },
}
