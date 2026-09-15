/**
 * Killzone scanner contracts (`/api/scanner/killzone`, W15). Pattern-flagging
 * only — never a signal, no execution path, no recommendation.
 */

export type KillzoneDirection = 'bullish' | 'bearish'
export type KillzoneBias = 'bullish' | 'bearish' | 'neutral'

export interface KillzoneCandidate {
  direction: KillzoneDirection
  sweep_time: number
  sweep_level: number
  shift_time: number
  shift_level: number
  killzone: string
  agrees_with_htf_bias: boolean
}

export interface LiquidityPool {
  type: 'BSL' | 'SSL'
  price: number
  source: string
  distance_from_price: number
  status: string
}

export interface FairValueGap {
  type: 'Bullish' | 'Bearish'
  top: number
  bottom: number
  creation_time: number
  age_candles: number
  status: string
}

export interface KillzoneScanResponse {
  ok: boolean
  symbol: string
  error: string | null

  ltf: string | null
  htf: string | null
  ltf_source: string | null
  htf_source: string | null

  htf_bias: KillzoneBias | null
  htf_structure: {
    trend: string
    recent_sequence: string
    last_break: string
    last_swing_high: number | null
    last_swing_low: number | null
  } | null
  htf_liquidity_targets: { bsl: LiquidityPool[]; ssl: LiquidityPool[] } | null
  current_killzone: string | null

  candidates: KillzoneCandidate[]
  recent_unmitigated_fvgs: FairValueGap[]

  disclaimer: string | null
  read_only: boolean
  live_broker_transmission: string
  timestamp: string
}
