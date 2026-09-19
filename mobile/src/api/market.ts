import type { CandlesResponse } from '../types/market'
import { apiGet } from './client'

/** GET /api/market/candles/{symbol} — OHLC candles for the scanner chart. */
export function getCandles(symbol: string, tf: string, count = 200, signal?: AbortSignal): Promise<CandlesResponse> {
  const params = new URLSearchParams({ tf, count: String(count) })
  return apiGet<CandlesResponse>(`/api/market/candles/${encodeURIComponent(symbol)}?${params.toString()}`, signal)
}
