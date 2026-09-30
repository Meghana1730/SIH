import { apiFetch } from '@/lib/api/client'
import type { TokenResponse, User } from '@/lib/api/types'

export const authApi = {
  login: (email: string, password: string) =>
    apiFetch<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    }),
  me: (signal?: AbortSignal) => apiFetch<User>('/api/v1/auth/me', { signal }),
}
