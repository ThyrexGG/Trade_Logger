import type { HealthResponse } from '../types/health'
import { apiGet } from './client'

/** GET /api/health — public, no login needed. */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/api/health', signal)
}
