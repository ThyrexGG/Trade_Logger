import { apiGet } from './client'
import type { PositionsResponse } from '../types/positions'

/** GET /api/positions — read-only open paper/shadow positions. */
export function getPositions(signal?: AbortSignal): Promise<PositionsResponse> {
  return apiGet<PositionsResponse>('/api/positions', { signal })
}
