import type { RiskPreviewRequest, RiskPreviewResponse } from '../types/risk'
import { apiPost } from './client'

/** POST /api/risk/preview — position size from the server's risk gateway. Calculation only; places no order. */
export function postRiskPreview(req: RiskPreviewRequest, signal?: AbortSignal): Promise<RiskPreviewResponse> {
  return apiPost<RiskPreviewResponse>('/api/risk/preview', req, signal)
}
