// Demo actions (recommendation decisions, employer validations, pledges, simulated events) are
// kept in this browser only (localStorage), because the backend has no endpoints for them yet.
// "Reset demo" on the Admin page clears them.

import { useSyncExternalStore } from 'react'

import type { EmployerActivity, RecommendationStatus } from '@/lib/api/types'

export type DemoState = {
  recommendationStatus: Record<string, RecommendationStatus>
  validations: Record<string, { agree: boolean; comment: string; at: string }>
  pledges: { course_id: string; seats: number; start_quarter: string; at: string }[]
  demandSubmissions: { role_code: string; headcount: number; skills: string[]; at: string }[]
  activity: EmployerActivity[]
  planActionStatus: Record<string, 'PLANNED' | 'IN_PROGRESS' | 'DONE'>
  evExpansionSimulated: boolean
  planSubmitted: boolean
}

const KEY = 'kaushalsetu.demo-state.v1'

const EMPTY: DemoState = {
  recommendationStatus: {},
  validations: {},
  pledges: [],
  demandSubmissions: [],
  activity: [],
  planActionStatus: {},
  evExpansionSimulated: false,
  planSubmitted: false,
}

function read(): DemoState {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...EMPTY, ...(JSON.parse(raw) as Partial<DemoState>) } : EMPTY
  } catch {
    return EMPTY
  }
}

let state: DemoState = read()
const listeners = new Set<() => void>()

export function getDemoState(): DemoState {
  return state
}

export function updateDemoState(change: (current: DemoState) => DemoState) {
  state = change(state)
  try {
    localStorage.setItem(KEY, JSON.stringify(state))
  } catch {
    // Storage blocked: the change lasts until the page is reloaded.
  }
  listeners.forEach((listener) => listener())
}

export function resetDemoState() {
  updateDemoState(() => EMPTY)
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useDemoState(): DemoState {
  return useSyncExternalStore(subscribe, getDemoState, getDemoState)
}
