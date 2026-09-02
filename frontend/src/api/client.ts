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

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      ...init,
    })
  } catch (cause) {
    throw new ApiError(`Network error contacting API at ${url}`, 0, { cause })
  }

  if (!response.ok) {
    throw new ApiError(
      `API request to ${path} failed with ${response.status}`,
      response.status,
    )
  }

  return (await response.json()) as T
}

export { API_BASE_URL }
