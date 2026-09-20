import { apiDelete, apiGet, apiPut } from './client'
import type { LossLimitStatus, LossLimitsInput, LossLimitsResponse } from '../types/lossLimits'

/** GET /api/loss-limits — every account with its limits and how close today's trading is to them. */
export function getLossLimits(signal?: AbortSignal): Promise<LossLimitsResponse> {
  return apiGet<LossLimitsResponse>('/api/loss-limits', { signal })
}

/** Save one account's limits. An empty value (null) means "no limit of that kind". */
export function saveLossLimits(account: string, body: LossLimitsInput): Promise<LossLimitStatus> {
  return apiPut<LossLimitStatus>(`/api/loss-limits/${encodeURIComponent(account)}`, body)
}

export function clearLossLimits(account: string): Promise<{ account_id: string; cleared: boolean }> {
  return apiDelete<{ account_id: string; cleared: boolean }>(`/api/loss-limits/${encodeURIComponent(account)}`)
}
