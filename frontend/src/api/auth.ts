import { apiGet, apiPost } from './client'

export interface AuthStatus {
  auth_required: boolean
  authenticated: boolean
  mode: 'passphrase' | 'supabase'
  timestamp: string
}

export interface AuthUser {
  id: string
  email: string
  display_name: string | null
  role: 'owner' | 'member'
}

export interface MeResult {
  mode: 'passphrase' | 'supabase'
  authenticated: boolean
  user: AuthUser | null
  error: string | null
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
 * GET /api/auth/me — supabase mode. With a valid Supabase session attached,
 * tells us whether this email is invited (`authenticated`) or still needs the
 * owner to add it to the allowlist (`error` explains which).
 */
export function getMe(signal?: AbortSignal): Promise<MeResult> {
  return apiGet<MeResult>('/api/auth/me', { signal })
}

/**
 * POST /api/auth/login — passphrase mode only. A wrong passphrase comes back as
 * HTTP 401 / 429; the client throws ApiError, so callers catch and read `.message`.
 */
export function login(password: string): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/login', { password })
}

export function logout(): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/logout', {})
}
