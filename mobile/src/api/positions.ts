import type { PositionsResponse } from '../types/positions'
import { apiGet } from './client'

/** GET /api/positions — the signed-in user's currently open positions. */
export function getPositions(signal?: AbortSignal): Promise<PositionsResponse> {
  return apiGet<PositionsResponse>('/api/positions', signal)
}
