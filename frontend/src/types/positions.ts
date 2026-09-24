/**
 * Response for GET /api/positions, mirroring api/schemas.py
 * (PositionItem / PositionsResponse). Read-only.
 */

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
  /** When the position was opened (the broker's own timestamp) — null only for a row synced
   * before this field existed. No explicit timezone in the string means UTC, same as exit_time. */
  open_time: string | null
  /** Subjective journal annotations, writable while the trade is still open
   * via PATCH /api/positions/{position_id} — carried over to the closed
   * trade's journal entry automatically once the position closes. */
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

/** Same editable-field shape as JournalUpdateRequest — the backend reuses
 * that schema for PATCH /api/positions/{position_id} too. */
export interface PositionUpdateRequest {
  setup_tag?: string
  notes?: string
  chart_snapshot_url?: string
  rating?: number
}

export interface PositionUpdateResponse {
  entry: PositionItem
  updated_fields: string[]
  writable: boolean
  source: string
  live_broker_transmission: string
  timestamp: string
}
