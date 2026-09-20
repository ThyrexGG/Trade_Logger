import type { LossLimitStatus, LossLimitsInput, LossLimitsResponse } from '../types/lossLimits'
import { apiDelete, apiGet, apiPut } from './client'

export function getLossLimits(signal?: AbortSignal): Promise<LossLimitsResponse> {
  return apiGet<LossLimitsResponse>('/api/loss-limits', signal)
}

/** Save one account's limits. An empty value (null) means "no limit of that kind". */
export function saveLossLimits(account: string, body: LossLimitsInput, signal?: AbortSignal): Promise<LossLimitStatus> {
  return apiPut<LossLimitStatus>(`/api/loss-limits/${encodeURIComponent(account)}`, body, signal)
}

export function clearLossLimits(account: string, signal?: AbortSignal): Promise<{ account_id: string; cleared: boolean }> {
  return apiDelete<{ account_id: string; cleared: boolean }>(`/api/loss-limits/${encodeURIComponent(account)}`, signal)
}
