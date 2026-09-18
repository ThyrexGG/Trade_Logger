import { apiGet, apiPatch } from './client'
import type { PositionsResponse, PositionUpdateRequest, PositionUpdateResponse } from '../types/positions'

/** GET /api/positions — read-only open paper/shadow positions. */
export function getPositions(signal?: AbortSignal): Promise<PositionsResponse> {
  return apiGet<PositionsResponse>('/api/positions', { signal })
}

/**
 * PATCH /api/positions/{position_id} — update the subjective annotations
 * (setup_tag / notes / chart_snapshot_url / rating) of one open position.
 * Never touches execution, orders or a broker.
 */
export function patchPosition(
  positionId: string,
  body: PositionUpdateRequest,
  signal?: AbortSignal,
): Promise<PositionUpdateResponse> {
  return apiPatch<PositionUpdateResponse>(
    `/api/positions/${encodeURIComponent(positionId)}`,
    body,
    { signal },
  )
}
