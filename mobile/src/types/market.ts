/** `/api/market/candles/{symbol}` — OHLC candles for a chart. Display only. */
export interface Candle {
  /** unix seconds */
  time: number
  open: number
  high: number
  low: number
  close: number
  volume?: number
}

export interface CandlesResponse {
  symbol: string
  timeframe: string
  count: number
  candles: Candle[]
  /** which feed served it: mt5 | binance | yahoo | synthetic_fallback */
  source: string
  liveness: string
}
