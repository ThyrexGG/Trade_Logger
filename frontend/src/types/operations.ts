/**
 * Response contracts for the Operations adapter (`/api/operations/*`) and the
 * reused positions endpoint.
 *
 * Journal = the authoritative `closed_trades` table. Audit = the
 * `execution_orders` operational execution trail. System = `/api/health`
 * values + `system_health.evaluate_system_health`. Mostly read-only; the one
 * exception is `ManualTradeInput` below (`POST /journal/trades`), for a trade
 * that never went through a broker sync. Nothing here submits an order,
 * modifies a position, or touches a broker either way.
 */

/** A hand-entered closed trade — money traded outside any broker sync.
 * profit/commission/swap are what the platform/broker actually reported,
 * not recomputed from price + volume (pip value varies by instrument). */
export interface ManualTradeInput {
  account_id: string
  symbol: string
  direction: 'BUY' | 'SELL'
  volume: number
  entry_price: number
  exit_price: number
  commission: number
  swap: number
  gross_profit: number
  /** ISO datetime strings (with timezone) — see toIsoWithZone in the form. */
  entry_time: string
  exit_time: string
  setup_tag?: string
  notes?: string
}

/** One exit of a position that was closed in pieces: "partial" for every exit but the last, "final" for the last. */
export interface TradeLeg {
  trade_id: string | null
  n: number
  kind: 'partial' | 'final'
  time: string
  /** unknown for a Capital.com partial (the broker repeats the last exit's size on every partial) */
  volume: number | null
  price: number | null
  net: number
}

export interface JournalTradeItem {
  trade_id: string
  account_id: string
  symbol: string
  direction: string
  volume: number
  entry_price: number
  exit_price: number
  commission: number
  swap: number
  gross_profit: number
  net_profit: number
  entry_time: string
  exit_time: string
  duration_minutes: number
  setup_tag: string | null
  notes: string | null
  rating: number | null
  chart_snapshot_url: string | null
  screenshot_count?: number
  /** Set when the position was closed in pieces: the P&L fields are then the whole position's totals. */
  legs?: TradeLeg[]
  /** some of the position is still open at the broker, so every leg so far is a partial */
  position_open?: boolean
}

export interface JournalScreenshotMeta {
  id: string
  trade_id: string
  filename: string | null
  mime: string
  byte_size: number
  caption: string | null
  created_at: string
  url: string
}

export interface JournalScreenshotsResponse {
  trade_id: string
  screenshots: JournalScreenshotMeta[]
  timestamp: string
}

/**
 * Editable journal annotations (Stage 12). Mirrors the legacy Streamlit
 * "Log & Review Trade Setup" form. Every execution / trade fact is immutable
 * and is rejected by the backend as an unknown field.
 */
export interface JournalUpdateRequest {
  setup_tag?: string
  notes?: string
  chart_snapshot_url?: string
  rating?: number
}

export type JournalEntryKind = 'idea' | 'review' | 'observation' | 'plan'

export interface JournalEntry {
  id: string
  kind: JournalEntryKind
  instrument: string | null
  title: string | null
  body: string
  tags: string[]
  screenshot_count: number
  created_at: string
  updated_at: string
}

export interface JournalEntryCreate {
  kind?: JournalEntryKind
  instrument?: string | null
  title?: string | null
  body?: string
  tags?: string[]
}

export interface JournalEntriesResponse {
  entries: JournalEntry[]
  timestamp: string
}

export interface JournalUpdateResponse {
  entry: JournalTradeItem
  updated_fields: string[]
  writable: boolean
  source: string
  live_broker_transmission: string
  timestamp: string
}

export interface JournalResponse {
  entries: JournalTradeItem[]
  total_trades: number
  wins: number
  losses: number
  total_net_profit: number
  accounts: string[]
  source: string
  writable: boolean
  timestamp: string
}

export interface AuditOrderItem {
  execution_id: string
  signal_id: string | null
  symbol: string | null
  side: string | null
  requested_quantity: number | null
  requested_entry: number | null
  stop_loss: number | null
  take_profit: number | null
  broker: string | null
  mode: string | null
  state: string | null
  reconciliation_status: string | null
  created_at: string | null
  submitted_at: string | null
  resolved_at: string | null
  filled_at: string | null
  execution_latency_ms: number | null
  reject_reason: string | null
  last_error: string | null
}

export interface AuditResponse {
  events: AuditOrderItem[]
  total_returned: number
  total_records: number
  state_counts: Record<string, number>
  mode_counts: Record<string, number>
  decision_ledger_records: number
  latest_event_at: string | null
  source: string
  read_only: boolean
  live_broker_transmission: string
  timestamp: string
}

export interface ReconciliationHealth {
  status: string | null
  healthy: boolean | null
  reason: string | null
  last_heartbeat: string | null
  last_success: string | null
  consecutive_failures: number | null
  iterations_count: number | null
}

export interface SystemSafetyGate {
  overall_status: string
  automation_allowed: boolean
  reasons: string[]
  kill_switch_engaged: boolean | null
  emergency_halt_engaged: boolean | null
  database_connected: boolean | null
  unresolved_unknown_orders_count: number | null
  reconciliation: ReconciliationHealth | null
}

export interface OperationsSystemResponse {
  api_status: string
  app_name: string
  version: string
  live_automation_enabled: boolean
  live_broker_transmission: string
  safety_gate: SystemSafetyGate
  open_positions: number
  timestamp: string
}
