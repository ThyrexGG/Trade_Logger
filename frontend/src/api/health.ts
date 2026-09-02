import { apiGet } from './client'
import type { HealthResponse } from '../types/health'

/** GET /api/health — lightweight backend status + fail-closed safety gate config. */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/api/health', { signal })
}
