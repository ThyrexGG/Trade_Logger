import type { LoginResult, MeResult } from '../types/auth'
import { apiGet, apiPost } from './client'

/** POST /api/auth/login (multiuser mode: email + password). Throws ApiError with the server's message on 401/403/429. */
export function login(email: string, password: string, signal?: AbortSignal): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/login', { email, password }, signal)
}

/** GET /api/auth/me — who the stored token belongs to, or `authenticated: false`. */
export function getMe(signal?: AbortSignal): Promise<MeResult> {
  return apiGet<MeResult>('/api/auth/me', signal)
}

/** POST /api/auth/logout — revokes the token server-side. */
export function logout(): Promise<LoginResult> {
  return apiPost<LoginResult>('/api/auth/logout', {})
}
