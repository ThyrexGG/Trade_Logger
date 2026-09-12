import { getWatchlist } from '../api/market'
import type { WatchlistItem, WatchlistResponse } from '../types/market'
import { useCachedResource } from './dataCache'

export type LoadState = 'loading' | 'ready' | 'error'

interface UseWatchlistResult {
  state: LoadState
  items: WatchlistItem[]
  /** Backend-provided response timestamp (ISO). Never synthesized here. */
  updatedAt: string | null
  error: string | null
  /** True when a background refresh is running over already-loaded data. */
  refreshing: boolean
  refetch: () => void
}

const REFRESH_MS = 20_000

/**
 * Module-cached: revisiting the watchlist within the reuse window renders the
 * last snapshot instantly while a background refresh confirms it's current.
 * One request for the whole list — never per symbol.
 */
export function useWatchlist(): UseWatchlistResult {
  const res = useCachedResource<WatchlistResponse>('watchlist', (signal) => getWatchlist(signal), {
    refreshMs: REFRESH_MS,
  })
  return {
    state: res.state,
    items: res.data?.items ?? [],
    updatedAt: res.data?.timestamp ?? null,
    error: res.error,
    refreshing: res.refreshing,
    refetch: res.refetch,
  }
}
