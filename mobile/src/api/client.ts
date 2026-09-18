import { API_BASE_URL, REQUEST_TIMEOUT_MS } from '../config'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** M2 registers this so every request carries `Authorization: Bearer <token>`. */
let tokenProvider: (() => string | null) | null = null
export function setTokenProvider(fn: (() => string | null) | null): void {
  tokenProvider = fn
}

async function request<T>(method: string, path: string, signal?: AbortSignal): Promise<T> {
  // fetch() has no built-in timeout; a dead network on a phone would otherwise hang forever.
  const timeout = new AbortController()
  const timer = setTimeout(() => timeout.abort(), REQUEST_TIMEOUT_MS)
  const onOuterAbort = () => timeout.abort()
  signal?.addEventListener('abort', onOuterAbort)

  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = tokenProvider?.()
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method, headers, signal: timeout.signal })
  } catch {
    throw new ApiError('Cannot reach the TradeLogger server.', 0)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onOuterAbort)
  }

  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed (${response.status}).`, response.status)
  }
  return (await response.json()) as T
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>('GET', path, signal)
}
