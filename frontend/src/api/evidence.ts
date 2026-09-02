import { apiGet } from './client'
import type { ForwardEvidenceState } from '../types/evidence'

/**
 * GET /api/forward-evidence/state — authoritative forward statistical
 * monitoring state (metrics, uncertainty, alpha-decay surveillance, milestone
 * progression, decision state, dataset provenance, holdout comparison).
 *
 * The adapter serves this from the Stage 3.5D read-snapshot cache (60s TTL);
 * a GET never mutates evidence state.
 */
export function getForwardEvidenceState(
  signal?: AbortSignal,
): Promise<ForwardEvidenceState> {
  return apiGet<ForwardEvidenceState>('/api/forward-evidence/state', { signal })
}
