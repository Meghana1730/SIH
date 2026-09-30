// Who is using the app. Two modes:
//   'api'     signed in to the FastAPI backend (a bearer token in sessionStorage)
//   'offline' "Enter demo" without the backend: every page shows demo data, badged as such
import { createContext, useContext } from 'react'

import type { User, UserRole } from '@/lib/api/types'

export type SessionMode = 'api' | 'offline'

export type Session = {
  user: User | null
  mode: SessionMode | null
  ready: boolean
  login: (email: string, password: string) => Promise<void>
  enterDemo: (role?: UserRole) => Promise<SessionMode>
  logout: () => void
}

export const SessionContext = createContext<Session | null>(null)

export function useSession(): Session {
  const session = useContext(SessionContext)
  if (!session) throw new Error('useSession must be used inside <SessionProvider>')
  return session
}

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Platform admin',
  state_officer: 'State officer',
  district_officer: 'District officer',
  ssc_reviewer: 'SSC reviewer',
  institute_admin: 'Institute admin',
  employer: 'Employer',
  candidate: 'Candidate',
}
