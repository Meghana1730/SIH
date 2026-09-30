// Central HTTP client. In development Vite forwards /api and /health to the FastAPI backend
// (vite.config.ts), so relative paths work and no CORS setup is needed.
//
// Every service in this folder goes through apiFetch(). Services for features the backend
// does not have yet return deterministic demo data instead (see withFallback and src/lib/demo),
// always marked source: 'demo' so the UI can badge it.

import { DEMO_FALLBACK_ENABLED } from '@/lib/demo/config'

export const API_BASE = '/api/v1'
const TOKEN_KEY = 'kaushalsetu.token'

export class ApiError extends Error {
  status: number
  code: string | undefined

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage blocked: the session simply is not remembered.
  }
}

type FetchOptions = {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
  auth?: boolean
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, auth = true } = options
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = auth ? getToken() : null
  if (token) headers.Authorization = `Bearer ${token}`
  let response: Response
  try {
    response = await fetch(path.startsWith('/') ? path : `${API_BASE}/${path}`, {
      method,
      headers,
      signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'The KaushalSetu API is not reachable.', 'NETWORK')
  }
  if (!response.ok) {
    let message = `${path} returned HTTP ${response.status}`
    let code: string | undefined
    try {
      const payload = await response.json()
      const detail = payload?.detail ?? payload?.error
      if (typeof detail === 'string') message = detail
      else if (detail?.message) {
        message = detail.message
        code = detail.code
      }
    } catch {
      // Not JSON: keep the generic message.
    }
    throw new ApiError(response.status, message, code)
  }
  return (await response.json()) as T
}

/** Where a piece of data came from. The UI shows a badge for anything that is not 'live'. */
export type DataSource = 'live' | 'demo'

export type Sourced<T> = {
  data: T
  source: DataSource
  /** Why demo data is shown (e.g. "Backend endpoint not built yet"). */
  note?: string
}

export const NOT_BUILT = 'This feature has no backend endpoint yet: showing deterministic demo data.'

/**
 * Try the real API; if it fails (API down, not logged in, endpoint missing) and demo fallback is
 * enabled, return the demo data marked source: 'demo'. With fallback disabled, errors surface.
 */
export async function withFallback<T>(
  live: (() => Promise<T>) | null,
  demo: () => T,
  note = NOT_BUILT,
): Promise<Sourced<T>> {
  if (live) {
    try {
      return { data: await live(), source: 'live' }
    } catch (error) {
      if (!DEMO_FALLBACK_ENABLED) throw error
      return { data: demo(), source: 'demo', note: fallbackNote(error) }
    }
  }
  if (!DEMO_FALLBACK_ENABLED) throw new ApiError(501, NOT_BUILT, 'NOT_BUILT')
  return { data: demo(), source: 'demo', note }
}

/** withFallback for demo data that loads asynchronously (e.g. the lazily loaded snapshot). */
export async function withFallbackAsync<T>(
  live: () => Promise<T>,
  demo: () => Promise<T>,
): Promise<Sourced<T>> {
  try {
    return { data: await live(), source: 'live' }
  } catch (error) {
    if (!DEMO_FALLBACK_ENABLED) throw error
    return { data: await demo(), source: 'demo', note: fallbackNote(error) }
  }
}

function fallbackNote(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return 'API offline: showing demo data.'
    if (error.status === 401) return 'Not signed in to the API: showing demo data.'
    if (error.status === 403) return 'Outside your access scope: showing demo data.'
    if (error.status === 404) return 'No analytics results in the API yet: showing demo data.'
  }
  return 'The API request failed: showing demo data.'
}
