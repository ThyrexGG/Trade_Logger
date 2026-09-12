import { getAnalyticsPerformance } from '../api/analytics'
import type { AnalyticsPerformanceResponse, AnalyticsQuery } from '../types/analytics'
import { useCachedResource, type CachedResource } from './dataCache'

type UseAnalyticsResult = Omit<CachedResource<AnalyticsPerformanceResponse>, 'setLocal'>

const DEBOUNCE_MS = 300

/**
 * One aggregated GET per filter set, module-cached: switching filters back to
 * a combination already fetched this session renders instantly instead of
 * re-showing a skeleton. Filter changes are debounced (300ms) so a
 * multi-select or a date drag fires a single request, not a storm. No
 * polling — analytics only changes when new trades sync (`tl:synced`).
 */
export function useAnalytics(query: AnalyticsQuery): UseAnalyticsResult {
  const key = JSON.stringify({
    account: query.account ?? 'ALL',
    symbols: [...(query.symbols ?? [])].sort(),
    start: query.start ?? null,
    end: query.end ?? null,
    initial_balance: query.initial_balance ?? null,
  })

  return useCachedResource(
    `analytics:${key}`,
    (signal) => getAnalyticsPerformance(query, signal),
    { debounceMs: DEBOUNCE_MS, revalidateOn: ['tl:synced'] },
  )
}
