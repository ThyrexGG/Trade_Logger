/**
 * Minimal typed API client for the TradeLogger FastAPI adapter layer.
 *
 * All calls go through HTTP. React never imports Python engines and never
 * duplicates trading logic — the adapter is the only boundary.
 *
 * Base URL resolution:
 *  - VITE_API_BASE_URL (if set) is prepended to every request path.
 *  - When empty (the development default) requests stay relative and the Vite
 *    dev proxy forwards /api/* to the local FastAPI server.
 */
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number, options?: ErrorOptions) {
    super(message, options)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Session cookie must ride along on every request (same-origin in dev, and
 * cross-origin in a hosted build where the API is on another domain).
 */
const CREDENTIALS: RequestCredentials = 'include'

let onUnauthorized: (() => void) | null = null

/** The auth layer registers a callback so a 401 anywhere bounces to the login screen. */
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn
}

let authTokenProvider: (() => Promise<string | null>) | null = null

/**
 * The Supabase auth layer (W8) registers a getter for the current access token.
 * When set, every request carries `Authorization: Bearer <token>`. Passphrase
 * mode leaves this null and relies on the session cookie instead.
 */
export function setAuthTokenProvider(fn: (() => Promise<string | null>) | null): void {
  authTokenProvider = fn
}

async function authHeaders(): Promise<Record<string, string>> {
  if (!authTokenProvider) return {}
  try {
    const token = await authTokenProvider()
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}

function noteResponse(response: Response): Response {
  // The login/logout/status calls handle their own 401s — a wrong passphrase
  // must not trigger the global "session expired" bounce.
  if (response.status === 401 && onUnauthorized && !response.url.includes('/api/auth/')) {
    onUnauthorized()
  }
  return response
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json', ...(await authHeaders()) },
      ...init,
      credentials: CREDENTIALS,
    })
  } catch (cause) {
    throw new ApiError(`Network error contacting API at ${url}`, 0, { cause })
  }
  noteResponse(response)

  if (!response.ok) {
    throw new ApiError(
      `API request to ${path} failed with ${response.status}`,
      response.status,
    )
  }

  return (await response.json()) as T
}

/** Best-effort extraction of a human-readable message from a FastAPI error body. */
async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((d) =>
          d && typeof d === 'object' && 'msg' in d
            ? String((d as { msg: unknown }).msg)
            : JSON.stringify(d),
        )
        .join('; ')
    }
  } catch {
    /* not JSON — fall through */
  }
  return null
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  init?: RequestInit,
): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify(body),
      ...init,
      credentials: CREDENTIALS,
    })
  } catch (cause) {
    throw new ApiError(`Network error contacting API at ${url}`, 0, { cause })
  }
  noteResponse(response)

  if (!response.ok) {
    const detail = await readErrorDetail(response)
    throw new ApiError(
      detail ?? `API request to ${path} failed with ${response.status}`,
      response.status,
    )
  }

  return (await response.json()) as T
}

export async function apiPut<T>(
  path: string,
  body: unknown,
  init?: RequestInit,
): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      method: 'PUT',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify(body),
      ...init,
      credentials: CREDENTIALS,
    })
  } catch (cause) {
    throw new ApiError(`Network error contacting API at ${url}`, 0, { cause })
  }
  noteResponse(response)

  if (!response.ok) {
    const detail = await readErrorDetail(response)
    throw new ApiError(
      detail ?? `API request to ${path} failed with ${response.status}`,
      response.status,
    )
  }

  return (await response.json()) as T
}

export async function apiPatch<T>(
  path: string,
  body: unknown,
  init?: RequestInit,
): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      method: 'PATCH',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify(body),
      ...init,
      credentials: CREDENTIALS,
    })
  } catch (cause) {
    throw new ApiError(`Network error contacting API at ${url}`, 0, { cause })
  }
  noteResponse(response)

  if (!response.ok) {
    const detail = await readErrorDetail(response)
    throw new ApiError(
      detail ?? `API request to ${path} failed with ${response.status}`,
      response.status,
    )
  }

  return (await response.json()) as T
}

export async function apiDelete<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      method: 'DELETE',
      headers: { Accept: 'application/json', ...(await authHeaders()) },
      ...init,
      credentials: CREDENTIALS,
    })
  } catch (cause) {
    throw new ApiError(`Network error contacting API at ${url}`, 0, { cause })
  }
  noteResponse(response)

  if (!response.ok) {
    const detail = await readErrorDetail(response)
    throw new ApiError(
      detail ?? `API request to ${path} failed with ${response.status}`,
      response.status,
    )
  }

  return (await response.json()) as T
}

export { API_BASE_URL }
