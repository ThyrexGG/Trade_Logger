import type { PositionItem, PositionsResponse, PositionUpdateRequest } from '../types/positions'
import { apiGet, apiPatch } from './client'

/** GET /api/positions — the signed-in user's currently open positions. */
export function getPositions(signal?: AbortSignal): Promise<PositionsResponse> {
  return apiGet<PositionsResponse>('/api/positions', signal)
}

/** PATCH /api/positions/{id} — journal an open trade; the notes carry over to the closed trade automatically. */
export function patchPosition(
  positionId: string,
  body: PositionUpdateRequest,
  signal?: AbortSignal,
): Promise<{ entry: PositionItem; updated_fields: string[] }> {
  return apiPatch<{ entry: PositionItem; updated_fields: string[] }>(
    `/api/positions/${encodeURIComponent(positionId)}`,
    body,
    signal,
  )
}
