// Recommendations (decision inbox). No backend endpoint yet: demo data, with decisions and
// employer validations kept in this browser (src/lib/demo/store.ts).

import { withFallback, type Sourced } from '@/lib/api/client'
import type { Recommendation, RecommendationStatus } from '@/lib/api/types'
import { RECOMMENDATIONS } from '@/lib/demo/recommendations'
import { getDemoState, updateDemoState } from '@/lib/demo/store'

function withState(rec: Recommendation): Recommendation {
  const state = getDemoState()
  const validated = state.validations[rec.id]
  return {
    ...rec,
    status: state.recommendationStatus[rec.id] ?? rec.status,
    employer_validations: rec.employer_validations + (validated?.agree ? 1 : 0),
  }
}

export const recommendationsApi = {
  list: (): Promise<Sourced<Recommendation[]>> =>
    withFallback(null, () =>
      RECOMMENDATIONS.map(withState).sort((a, b) => b.priority_score - a.priority_score),
    ),

  get: async (id: string): Promise<Sourced<Recommendation | null>> => {
    const all = await recommendationsApi.list()
    return { ...all, data: all.data.find((r) => r.id === id) ?? null }
  },

  setStatus: async (id: string, status: RecommendationStatus) => {
    updateDemoState((s) => ({
      ...s,
      recommendationStatus: { ...s.recommendationStatus, [id]: status },
    }))
    return { id, status }
  },
}
