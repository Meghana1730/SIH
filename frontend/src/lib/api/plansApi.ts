// District skill plans. No backend endpoint yet: the Nashik plan is demo data, updated with the
// demo actions taken in this browser (apprenticeship pledges, action progress, submission).

import { withFallback, type Sourced } from '@/lib/api/client'
import type { DistrictPlan } from '@/lib/api/types'
import { OFFERINGS } from '@/lib/demo/catalog'
import { NASHIK_PLAN } from '@/lib/demo/people'
import { RECOMMENDATIONS } from '@/lib/demo/recommendations'
import { getDemoState, updateDemoState } from '@/lib/demo/store'

function current(): DistrictPlan[] {
  const state = getDemoState()
  const nashikPledges = state.pledges.filter((p) =>
    OFFERINGS.some((o) => o.id === p.course_id && o.district.code === 'MH-NASHIK'),
  )
  const seats = nashikPledges.reduce((sum, p) => sum + p.seats, 0)
  const validated = Object.entries(state.validations).filter(
    ([id, v]) =>
      v.agree && RECOMMENDATIONS.some((r) => r.id === id && r.district.code === 'MH-NASHIK'),
  ).length
  const plan: DistrictPlan = {
    ...NASHIK_PLAN,
    status: state.planSubmitted ? 'IN_REVIEW' : NASHIK_PLAN.status,
    actions: NASHIK_PLAN.actions.map((a) => ({
      ...a,
      status:
        state.planActionStatus[a.id] ??
        (a.id === 'act-2' && validated
          ? 'DONE'
          : a.id === 'act-3' && seats
            ? 'IN_PROGRESS'
            : a.status),
    })),
    commitments: [
      ...NASHIK_PLAN.commitments,
      { label: 'Apprenticeship seats pledged', value: String(seats) },
      { label: 'Employer validations received', value: String(validated) },
    ],
  }
  return [plan]
}

export const plansApi = {
  list: (): Promise<Sourced<DistrictPlan[]>> => withFallback(null, current),
  get: async (district: string): Promise<Sourced<DistrictPlan | null>> => {
    const all = await plansApi.list()
    return { ...all, data: all.data.find((p) => p.district.code === district) ?? null }
  },
  setActionStatus: async (actionId: string, status: 'PLANNED' | 'IN_PROGRESS' | 'DONE') => {
    updateDemoState((s) => ({
      ...s,
      planActionStatus: { ...s.planActionStatus, [actionId]: status },
    }))
  },
  submit: async () => {
    updateDemoState((s) => ({ ...s, planSubmitted: true }))
  },
}
