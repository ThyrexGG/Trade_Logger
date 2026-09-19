import { API_BASE_URL, REQUEST_TIMEOUT_MS } from '../config'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** The auth layer registers this so every request carries `Authorization: Bearer <token>`. */
let tokenProvider: (() => string | null) | null = null
export function setTokenProvider(fn: (() => string | null) | null): void {
  tokenProvider = fn
}

/** A 401 on any non-auth route means the session ended — bounce to the login screen. */
let unauthorizedHandler: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn
}

/** Best-effort human-readable message from a FastAPI error body. */
async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown; error?: unknown }
    // Auth endpoints answer with a model that carries `error`; the rest use FastAPI's `detail`.
    if (typeof body?.error === 'string' && body.error) return body.error
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
        .join('; ')
    }
  } catch {
    /* not JSON */
  }
  return null
}

async function request<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  // fetch() has no built-in timeout; a dead network on a phone would otherwise hang forever.
  const timeout = new AbortController()
  const timer = setTimeout(() => timeout.abort(), REQUEST_TIMEOUT_MS)
  const onOuterAbort = () => timeout.abort()
  signal?.addEventListener('abort', onOuterAbort)

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = tokenProvider?.()
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: timeout.signal,
    })
  } catch {
    throw new ApiError('Cannot reach the TradeLogger server. Check your connection.', 0)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onOuterAbort)
  }

  if (response.status === 401 && !path.startsWith('/api/auth/')) unauthorizedHandler?.()

  if (!response.ok) {
    const detail = await readErrorDetail(response)
    throw new ApiError(detail ?? `Request to ${path} failed (${response.status}).`, response.status)
  }
  return (await response.json()) as T
}

export const apiGet = <T>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, signal)
export const apiPost = <T>(path: string, body: unknown, signal?: AbortSignal) => request<T>('POST', path, body, signal)
export const apiPatch = <T>(path: string, body: unknown, signal?: AbortSignal) => request<T>('PATCH', path, body, signal)
export const apiDelete = <T>(path: string, signal?: AbortSignal) => request<T>('DELETE', path, undefined, signal)
