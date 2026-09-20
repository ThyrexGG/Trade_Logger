import { API_BASE_URL, REQUEST_TIMEOUT_MS, UPLOAD_TIMEOUT_MS } from '../config'

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

/** Headers for loading protected images (expo-image sends these with the request). */
export function authHeaders(): Record<string, string> {
  const token = tokenProvider?.()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** A 401 on any non-auth route means the session ended — bounce to the login screen. */
let unauthorizedHandler: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn
}

/** Best-effort human-readable message from a parsed FastAPI error body. */
function detailFromBody(parsed: unknown): string | null {
  const body = parsed as { detail?: unknown; error?: unknown } | null
  // Auth endpoints answer with a model that carries `error`; the rest use FastAPI's `detail`.
  if (typeof body?.error === 'string' && body.error) return body.error
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
      .join('; ')
  }
  return null
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    return detailFromBody(await response.json())
  } catch {
    return null // not JSON
  }
}

async function request<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
  signal?: AbortSignal,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<T> {
  // fetch() has no built-in timeout; a dead network on a phone would otherwise hang forever.
  const timeout = new AbortController()
  const timer = setTimeout(() => timeout.abort(), timeoutMs)
  const onOuterAbort = () => timeout.abort()
  signal?.addEventListener('abort', onOuterAbort)

  const headers: Record<string, string> = { Accept: 'application/json' }
  // A FormData body must NOT get a Content-Type: fetch adds the multipart boundary itself.
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  const token = tokenProvider?.()
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
      signal: timeout.signal,
    })
  } catch (err) {
    console.warn(`[api] ${method} ${path} failed before a response:`, err instanceof Error ? err.message : err)
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
export const apiPut = <T>(path: string, body: unknown, signal?: AbortSignal) => request<T>('PUT', path, body, signal)
export const apiPatch = <T>(path: string, body: unknown, signal?: AbortSignal) => request<T>('PATCH', path, body, signal)
export const apiDelete = <T>(path: string, signal?: AbortSignal) => request<T>('DELETE', path, undefined, signal)

/** For reads that fetch market data on the server first (the scanner) — slower than a database read. */
export const apiGetSlow = <T>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, signal, 45_000)

/** For calls that wait on a language model — a reply can take well over the normal timeout. */
export const apiPostSlow = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>('POST', path, body, signal, 90_000)

/**
 * Multipart upload (screenshots). Uses XMLHttpRequest on purpose: since Expo SDK 52 the global fetch is a
 * spec-strict implementation that rejects React Native's `{ uri, name, type }` file parts with
 * "Unsupported FormDataPart implementation"; XHR still sends them natively.
 */
export function apiPostForm<T>(path: string, form: FormData, signal?: AbortSignal, timeoutMs: number = UPLOAD_TIMEOUT_MS): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const fail = (why: string) => {
      console.warn(`[api] POST ${path} failed before a response: ${why}`)
      reject(new ApiError('Cannot reach the TradeLogger server. Check your connection.', 0))
    }
    xhr.open('POST', `${API_BASE_URL}${path}`)
    xhr.setRequestHeader('Accept', 'application/json')
    const token = tokenProvider?.()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`) // no Content-Type: the multipart boundary is added for us
    xhr.timeout = timeoutMs
    xhr.onload = () => {
      if (xhr.status === 401 && !path.startsWith('/api/auth/')) unauthorizedHandler?.()
      let parsed: unknown = null
      try {
        parsed = JSON.parse(xhr.responseText)
      } catch {
        /* not JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(parsed as T)
      else reject(new ApiError(detailFromBody(parsed) ?? `Request to ${path} failed (${xhr.status}).`, xhr.status))
    }
    xhr.onerror = () => fail('network error')
    xhr.ontimeout = () => fail('timed out')
    xhr.onabort = () => fail('aborted')
    signal?.addEventListener('abort', () => xhr.abort())
    xhr.send(form)
  })
}
