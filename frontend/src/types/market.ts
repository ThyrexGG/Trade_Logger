/**
 * Response shapes for the read-only market endpoints, mirroring
 * api/schemas.py (WatchlistItem / WatchlistResponse / MarketSnapshotResponse).
 * Kept in sync manually — thin typed views, no generated tooling. Only fields
 * the backend actually returns are declared here.
 */

export interface WatchlistItem {
  symbol: string
  display: string
  name: string
  asset_class: string
  price: number
  spread: number
  bias_4h: string
  bias_15m: string
  setup_state: string
  edge_score: number
  macro_score: number
  agreement_pct: number
  data_quality: number
  mode: string
}

export interface WatchlistResponse {
  items: WatchlistItem[]
  total_count: number
  asset_filter: string
  timestamp: string
}

/** Multi-timeframe bias hierarchy: keys "1D" | "4H" | "1H" | "15M" | "5M" | "1M". */
export type MtfBias = Record<string, string>

export interface MarketSnapshot {
  symbol: string
  display: string
  price: number
  bid: number
  ask: number
  spread: number
  session: string
  mtf_bias: MtfBias
  setup_state: string
  edge_score: number
  macro_score: number
  data_quality: number
  live_broker_transmission: string
  cached: boolean
  timestamp: string
}
