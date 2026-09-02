import { apiGet } from './client'
import type { MarketSnapshot, WatchlistResponse } from '../types/market'

/** GET /api/watchlist — the full configured watchlist in one request. */
export function getWatchlist(signal?: AbortSignal): Promise<WatchlistResponse> {
  return apiGet<WatchlistResponse>('/api/watchlist', { signal })
}

/** GET /api/market/snapshot/{symbol} — one snapshot for the selected symbol. */
export function getMarketSnapshot(
  symbol: string,
  signal?: AbortSignal,
): Promise<MarketSnapshot> {
  return apiGet<MarketSnapshot>(
    `/api/market/snapshot/${encodeURIComponent(symbol)}`,
    { signal },
  )
}
