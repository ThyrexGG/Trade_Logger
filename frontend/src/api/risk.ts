import { apiPost } from './client'
import type { RiskPreviewRequest, RiskPreviewResponse } from '../types/risk'

/**
 * POST /api/risk/preview — authoritative pre-trade sizing from risk_gateway.py.
 * Calculation-only: transmits no orders, mutates no state.
 */
export function postRiskPreview(
  req: RiskPreviewRequest,
  signal?: AbortSignal,
): Promise<RiskPreviewResponse> {
  return apiPost<RiskPreviewResponse>('/api/risk/preview', req, { signal })
}
