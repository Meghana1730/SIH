// Employer demand, recommendation validation and apprenticeship pledges. No backend endpoints
// yet: submissions are kept in this browser as demo data (src/lib/demo/store.ts).

import { withFallback, type Sourced } from '@/lib/api/client'
import type {
  ApprenticeshipPledge,
  Employer,
  EmployerActivity,
  EmployerDemandSubmission,
} from '@/lib/api/types'
import { OFFERINGS, ROLES } from '@/lib/demo/catalog'
import { EMPLOYERS } from '@/lib/demo/people'
import { RECOMMENDATIONS } from '@/lib/demo/recommendations'
import { getDemoState, updateDemoState } from '@/lib/demo/store'

function stamp(): string {
  return new Date().toISOString()
}

function log(kind: EmployerActivity['kind'], text: string) {
  updateDemoState((s) => ({
    ...s,
    activity: [
      {
        id: `${kind}-${s.activity.length + 1}`,
        kind,
        text,
        at: stamp(),
        is_synthetic: true as const,
      },
      ...s.activity,
    ],
  }))
}

export const employerApi = {
  list: (): Promise<Sourced<Employer[]>> => withFallback(null, () => EMPLOYERS),

  submitDemand: async (submission: EmployerDemandSubmission) => {
    if (submission.headcount < 1 || submission.headcount > 500) {
      throw new Error('Headcount must be between 1 and 500.')
    }
    const role = ROLES.find((r) => r.code === submission.role_code)
    updateDemoState((s) => ({
      ...s,
      demandSubmissions: [
        ...s.demandSubmissions,
        {
          role_code: submission.role_code,
          headcount: submission.headcount,
          skills: submission.skills,
          at: stamp(),
        },
      ],
    }))
    log(
      'DEMAND',
      `Requested ${submission.headcount} x ${role?.title ?? submission.role_code} within ${submission.horizon_months} months`,
    )
    return submission
  },

  validate: async (recommendationId: string, agree: boolean, comment: string) => {
    const rec = RECOMMENDATIONS.find((r) => r.id === recommendationId)
    updateDemoState((s) => ({
      ...s,
      validations: {
        ...s.validations,
        [recommendationId]: { agree, comment, at: stamp() },
      },
    }))
    log('VALIDATION', `${agree ? 'Endorsed' : 'Disagreed with'}: ${rec?.title ?? recommendationId}`)
    return { recommendationId, agree }
  },

  pledge: async (pledge: ApprenticeshipPledge) => {
    if (pledge.seats < 1 || pledge.seats > 200) {
      throw new Error('Seats must be between 1 and 200.')
    }
    const offering = OFFERINGS.find((o) => o.id === pledge.course_id)
    updateDemoState((s) => ({
      ...s,
      pledges: [
        ...s.pledges,
        {
          course_id: pledge.course_id,
          seats: pledge.seats,
          start_quarter: pledge.start_quarter,
          at: stamp(),
        },
      ],
    }))
    log(
      'PLEDGE',
      `Pledged ${pledge.seats} apprenticeship seats from ${pledge.start_quarter} for ${offering?.institute.name ?? pledge.course_id}`,
    )
    return pledge
  },

  activity: (): Promise<Sourced<EmployerActivity[]>> =>
    withFallback(null, () => getDemoState().activity),
}
