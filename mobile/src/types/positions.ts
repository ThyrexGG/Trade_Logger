/** Mirrors api/schemas.py PositionItem / PositionsResponse (kept in sync by hand). */
export interface PositionItem {
  position_id: string
  symbol: string
  direction: string
  volume: number
  entry_price: number
  current_price: number
  sl: number
  tp: number
  floating_pnl: number
  unrealized_r: string
  mae: string
  mfe: string
  account_id: string
  /** Journal annotations, writable while the trade is open (M5). */
  setup_tag: string | null
  notes: string | null
  chart_snapshot_url: string | null
  rating: number | null
  screenshot_count?: number
}

export interface PositionsResponse {
  positions: PositionItem[]
  total_open: number
  total_floating_pnl: number
  timestamp: string
}

/** PATCH /api/positions/{id} body — same shape as the journal update. */
export interface PositionUpdateRequest {
  setup_tag?: string
  notes?: string
  chart_snapshot_url?: string
  rating?: number
}
