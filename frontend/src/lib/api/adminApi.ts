// Admin: system health, users and audit log (live, admin only) and the demo controls.

import { analyticsApi } from '@/lib/api/analyticsApi'
import { apiFetch } from '@/lib/api/client'
import type { ApiHealth, AuditEntry, DbHealth, User } from '@/lib/api/types'
import { resetDemoState, updateDemoState } from '@/lib/demo/store'

export const adminApi = {
  health: (signal?: AbortSignal) => apiFetch<ApiHealth>('/health', { signal, auth: false }),
  dbHealth: (signal?: AbortSignal) => apiFetch<DbHealth>('/health/db', { signal, auth: false }),
  users: () => apiFetch<User[]>('/api/v1/admin/users'),
  auditLog: (limit = 50) => apiFetch<AuditEntry[]>(`/api/v1/admin/audit-log?limit=${limit}`),

  /** Recompute demand -> supply -> mismatch on the backend (admin). */
  runPipeline: () => analyticsApi.run(),

  /** Clear every demo action stored in this browser. */
  resetDemo: async () => resetDemoState(),

  /**
   * Show the demo world's simulated Nashik EV event across the app (banner, notification,
   * market signal). The event itself (and its ~180 jobs) is part of the synthetic data.
   */
  simulateEvExpansion: async (on = true) =>
    updateDemoState((s) => ({ ...s, evExpansionSimulated: on })),
}
