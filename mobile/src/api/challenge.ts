import type { ChallengeConfigInput, ChallengePhase, ChallengeStatus } from '../types/challenge'
import { apiDelete, apiGet, apiPost } from './client'

/** GET /api/challenge/status — `configured: false` (everything else null) when the account has no tracker yet. */
export function getChallengeStatus(account: string, signal?: AbortSignal): Promise<ChallengeStatus> {
  return apiGet<ChallengeStatus>(`/api/challenge/status?account=${encodeURIComponent(account)}`, signal)
}

/** Create the tracker, or edit its rules in place (phase progress is kept). */
export function saveChallengeConfig(body: ChallengeConfigInput, signal?: AbortSignal): Promise<ChallengeStatus> {
  return apiPost<ChallengeStatus>('/api/challenge/config', body, signal)
}

/** Mark the current phase passed. The live balance becomes the next phase's starting point. */
export function advanceChallenge(account: string, to: Exclude<ChallengePhase, '1'>, signal?: AbortSignal): Promise<ChallengeStatus> {
  return apiPost<ChallengeStatus>('/api/challenge/advance', { account_id: account, to }, signal)
}

/** Restart the attempt from Phase 1 (e.g. after buying a new evaluation). */
export function resetChallenge(account: string, signal?: AbortSignal): Promise<ChallengeStatus> {
  return apiPost<ChallengeStatus>('/api/challenge/reset', { account_id: account }, signal)
}

export function deleteChallengeConfig(account: string, signal?: AbortSignal): Promise<{ account_id: string; deleted: boolean }> {
  return apiDelete<{ account_id: string; deleted: boolean }>(`/api/challenge/config?account=${encodeURIComponent(account)}`, signal)
}
