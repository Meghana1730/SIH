// Helpers for evidence display and status colours (kept out of component files).
import type { Tone } from '@/components/badges'
import type { EvidenceItem, Reason } from '@/lib/api/types'

export type EvidenceLike = {
  title: string
  detail: string
  kind: EvidenceItem['kind']
  source?: string
}

export function reasonToEvidence(reason: Reason): EvidenceLike {
  return {
    title: REASON_TITLES[reason.code] ?? reason.code.replace(/_/g, ' '),
    detail: reason.text,
    kind: reason.is_synthetic ? 'SYNTHETIC' : 'OBSERVED',
    source: 'analytics API evidence',
  }
}

const REASON_TITLES: Record<string, string> = {
  postings_increased: 'Job postings rising',
  postings_decreased: 'Job postings falling',
  employer_demand_increased: 'Employers asking for more',
  employer_demand_decreased: 'Employers asking for fewer',
  industry_event: 'Industry event',
  skill_emerging: 'Emerging skill',
  skill_growing: 'Growing skill',
  skill_stable: 'Stable skill',
  skill_declining: 'Declining skill',
  training_supply_low: 'Training supply too low',
  training_supply_high: 'More trainees than openings',
  balanced: 'Supply matches openings',
  absorption: 'Trainee placement',
}

export function mismatchTone(score: number | null | undefined): Tone {
  if (score === null || score === undefined) return 'neutral'
  if (score >= 2.3) return 'danger'
  if (score >= 1.5) return 'warning'
  return 'success'
}
