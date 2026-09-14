import { apiDelete, apiGet, apiPost } from './client'
import type { ChallengeConfigInput, ChallengeStatus } from '../types/challenge'

/** GET /api/challenge/status — live phase/drawdown/daily-loss/profit-day snapshot. */
export function getChallengeStatus(account: string, signal?: AbortSignal): Promise<ChallengeStatus> {
  return apiGet<ChallengeStatus>(`/api/challenge/status?account=${encodeURIComponent(account)}`, { signal })
}

/** POST /api/challenge/config — create, or edit the rules on, an account's challenge. */
export function saveChallengeConfig(body: ChallengeConfigInput): Promise<ChallengeStatus> {
  return apiPost<ChallengeStatus>('/api/challenge/config', body)
}

/** POST /api/challenge/advance — mark the current phase passed, move to the next. */
export function advanceChallengePhase(accountId: string, to: '2' | 'funded'): Promise<ChallengeStatus> {
  return apiPost<ChallengeStatus>('/api/challenge/advance', { account_id: accountId, to })
}

/** POST /api/challenge/reset — restart the attempt from Phase 1. */
export function resetChallenge(accountId: string): Promise<ChallengeStatus> {
  return apiPost<ChallengeStatus>('/api/challenge/reset', { account_id: accountId })
}

/** DELETE /api/challenge/config — remove the tracker for this account entirely. */
export function deleteChallengeConfig(account: string): Promise<{ account_id: string; deleted: boolean }> {
  return apiDelete(`/api/challenge/config?account=${encodeURIComponent(account)}`)
}
