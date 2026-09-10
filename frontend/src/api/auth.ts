import { apiGet, apiPost } from './client'

export type AuthMode = 'passphrase' | 'multiuser' | 'supabase'

export interface AuthStatus {
  auth_required: boolean
  authenticated: boolean
  mode: AuthMode
  timestamp: string
}

export interface AuthUser {
  id: string
  email: string
  display_name: string | null
  role: 'owner' | 'member'
}

export interface MeResult {
  mode: AuthMode
  authenticated: boolean
  user: AuthUser | null
  error: string | null
  timestamp: string
}

export interface LoginResult {
  ok: boolean
  error: string | null
  expires_at: string | null
  token: string | null
  user: AuthUser | null
  timestamp: string
}

/** GET /api/auth/status — safe to call unauthenticated. */
export function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return apiGet<AuthStatus>('/api/auth/status', { signal })
}

/**
 * GET /api/auth/me — multiuser / supabase mode. Returns the signed-in account,
 * or `authenticated: false` with an `error` explaining why (session ended, or
 * the email is not on the invite list).
 */
export function getMe(signal?: AbortSignal): Promise<MeResult> {
  return apiGet<MeResult>('/api/auth/me', { signal })
}

/**
 * POST /api/auth/login.
 *  - passphrase mode: `login(passphrase)`
 *  - multiuser mode:  `login(password, email)`
 * A wrong credential comes back as HTTP 401 / 403 / 429 — the client throws
 * ApiError, so callers catch and read `.message`.
 */
export function login(password: string, email?: string): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/login', email ? { email, password } : { password })
}

/** POST /api/auth/signup — multiuser mode. Creates an invited account and signs in. */
export function signup(
  email: string,
  password: string,
  displayName?: string,
): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/signup', {
    email,
    password,
    ...(displayName ? { display_name: displayName } : {}),
  })
}

export function logout(): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/logout', {})
}
