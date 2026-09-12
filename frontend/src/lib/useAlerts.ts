import { getAlerts } from '../api/alerts'
import type { AlertsResponse } from '../types/alerts'
import { useCachedResource, type CachedResource } from './dataCache'

export type UseAlertsResult = CachedResource<AlertsResponse>

/**
 * Module-cached: revisiting Price Alerts within the reuse window renders the
 * last list instantly. Slow 60s poll otherwise — alert rows change rarely
 * (created/deleted here, or flipped to TRIGGERED by the standalone
 * `auto_sync` daemon); create/delete apply optimistically via `setLocal`
 * instead of waiting on this interval.
 */
const REFRESH_MS = 60_000

export function useAlerts(): UseAlertsResult {
  return useCachedResource('alerts', (signal) => getAlerts(signal), { refreshMs: REFRESH_MS })
}
