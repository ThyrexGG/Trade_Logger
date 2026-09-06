import { apiGet } from './client'
import type { CandlesResponse, MarketSnapshot, WatchlistResponse } from '../types/market'

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

/** GET /api/market/candles/{symbol} — OHLC candles for the live chart. */
export function getCandles(
  symbol: string,
  tf: string,
  count = 200,
  signal?: AbortSignal,
): Promise<CandlesResponse> {
  const p = new URLSearchParams({ tf, count: String(count) })
  return apiGet<CandlesResponse>(
    `/api/market/candles/${encodeURIComponent(symbol)}?${p.toString()}`,
    { signal },
  )
}
