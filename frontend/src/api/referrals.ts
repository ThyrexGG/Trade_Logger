import { apiGet, apiPost } from './client'

export type ReferralClaimStatus = 'pending' | 'verified' | 'rejected'

export interface ReferralClaim {
  id: string
  user_id: string
  partner_id: string
  note: string | null
  status: ReferralClaimStatus
  created_at: string
  reviewed_at: string | null
  reviewed_by: string | null
}

interface ClaimResponse {
  claim: ReferralClaim
}

interface MyClaimsResponse {
  claims: ReferralClaim[]
}

/** Self-report "I signed up with your link" for one partner. Idempotent —
 * calling this again for the same partner returns the existing claim rather
 * than creating a duplicate. */
export function claimReferral(partnerId: string, note?: string): Promise<ClaimResponse> {
  const qs = new URLSearchParams({ partner_id: partnerId })
  if (note) qs.set('note', note)
  return apiPost<ClaimResponse>(`/api/referrals/claim?${qs.toString()}`, {})
}

/** The current user's own claims, so the UI can show pending/verified/rejected. */
export function listMyReferralClaims(signal?: AbortSignal): Promise<MyClaimsResponse> {
  return apiGet<MyClaimsResponse>('/api/referrals/mine', { signal })
}
