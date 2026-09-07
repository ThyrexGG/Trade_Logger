import { apiGet, apiPost } from './client'

export interface AuthStatus {
  auth_required: boolean
  authenticated: boolean
  timestamp: string
}

export interface LoginResult {
  ok: boolean
  error: string | null
  expires_at: string | null
  timestamp: string
}

/** GET /api/auth/status — safe to call unauthenticated. */
export function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return apiGet<AuthStatus>('/api/auth/status', { signal })
}

/**
 * POST /api/auth/login. A wrong passphrase comes back as HTTP 401 / 429 — the
 * client throws ApiError for those, so callers catch and read `.message`.
 */
export function login(password: string): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/login', { password })
}

export function logout(): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/logout', {})
}
