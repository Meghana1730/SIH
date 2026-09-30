import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { SessionContext, type Session, type SessionMode } from '@/app/session'
import { authApi } from '@/lib/api/authApi'
import { getToken, setToken } from '@/lib/api/client'
import type { User, UserRole } from '@/lib/api/types'
import { DEMO_LOGIN } from '@/lib/demo/config'

const OFFLINE_KEY = 'kaushalsetu.offline-demo'

function offlineUser(role: UserRole): User {
  return {
    id: 'offline-demo',
    email: 'demo@kaushalsetu.example',
    display_name: 'Demo user (offline)',
    role,
    language: 'en',
    state_name: 'Maharashtra',
    district_id: null,
    institute_id: null,
    employer_id: null,
    candidate_id: null,
    is_active: true,
    is_demo: true,
    last_login_at: null,
    created_at: '2026-09-30T00:00:00Z',
  }
}

function readOffline(): UserRole | null {
  try {
    return sessionStorage.getItem(OFFLINE_KEY) as UserRole | null
  } catch {
    return null
  }
}

function writeOffline(role: UserRole | null) {
  try {
    if (role) sessionStorage.setItem(OFFLINE_KEY, role)
    else sessionStorage.removeItem(OFFLINE_KEY)
  } catch {
    // Storage blocked: the demo session lasts until reload.
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  // Without a token the session is known at once (offline demo or signed out); with a token
  // it is confirmed with /auth/me below.
  const [user, setUser] = useState<User | null>(() => {
    const offline = readOffline()
    return !getToken() && offline ? offlineUser(offline) : null
  })
  const [mode, setMode] = useState<SessionMode | null>(() =>
    !getToken() && readOffline() ? 'offline' : null,
  )
  const [ready, setReady] = useState(() => !getToken())

  useEffect(() => {
    if (!getToken()) return
    const controller = new AbortController()
    const offline = readOffline()
    authApi
      .me(controller.signal)
      .then((me) => {
        setUser(me)
        setMode('api')
      })
      .catch(() => {
        if (controller.signal.aborted) return
        setToken(null)
        if (offline) {
          setUser(offlineUser(offline))
          setMode('offline')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setReady(true)
      })
    return () => controller.abort()
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await authApi.login(email, password)
      setToken(result.access_token)
      writeOffline(null)
      setUser(result.user)
      setMode('api')
      await client.invalidateQueries()
    },
    [client],
  )

  const enterDemo = useCallback(
    async (role: UserRole = 'state_officer'): Promise<SessionMode> => {
      if (DEMO_LOGIN.email && DEMO_LOGIN.password) {
        try {
          await login(DEMO_LOGIN.email, DEMO_LOGIN.password)
          return 'api'
        } catch {
          // API unreachable or demo account missing: continue offline.
        }
      }
      setToken(null)
      writeOffline(role)
      setUser(offlineUser(role))
      setMode('offline')
      await client.invalidateQueries()
      return 'offline'
    },
    [client, login],
  )

  const logout = useCallback(() => {
    setToken(null)
    writeOffline(null)
    setUser(null)
    setMode(null)
    client.clear()
  }, [client])

  const value = useMemo<Session>(
    () => ({ user, mode, ready, login, enterDemo, logout }),
    [user, mode, ready, login, enterDemo, logout],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
