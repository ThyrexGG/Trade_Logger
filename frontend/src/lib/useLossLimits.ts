import { getLossLimits } from '../api/lossLimits'
import type { LossLimitsResponse } from '../types/lossLimits'
import { useCachedResource, type CachedResource } from './dataCache'

export type UseLossLimitsResult = CachedResource<LossLimitsResponse>

/** Module-cached like every other page resource. A 60s poll keeps "today's loss" honest while the tab is open;
 * saving or clearing a limit refetches straight away. */
export function useLossLimits(): UseLossLimitsResult {
  return useCachedResource('loss-limits', (signal) => getLossLimits(signal), { refreshMs: 60_000, revalidateOn: ['tl:synced'] })
}
