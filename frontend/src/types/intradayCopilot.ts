/**
 * Phase 100 — intraday setup co-pilot. Decision support for discretionary
 * intraday trading on the 11-instrument FX + gold 15m/1h/4h universe: named
 * structural conditions on the latest bar and their multi-year forward-outcome
 * base rates. NOT a signal generator — Phases 70–93 found no systematic
 * intraday directional edge, so it never recommends a trade.
 */
import type { SafetyBarrier } from './strategyResearch'

export interface CopilotScanInstrument {
  instrument: string
  timeframe: string
  bar_time: string
  close: number
  atr: number
  tr_atr: number
  regime: string
  session: string
  prior_day_high: number
  prior_day_low: number
  state: string
  active_conditions: string[]
  active_condition_notes: Record<string, string>
}

export interface CopilotUniverseScan {
  timeframe: string
  generated_at: string
  note: string
  instruments: CopilotScanInstrument[]
  conditions_active_somewhere: Record<string, string[]>
}

export interface CopilotHorizonOutcome {
  horizon_bars: number
  n: number
  up_rate: number
  down_rate: number
  mean_fwd_ret: number
  median_fwd_ret: number
  p25_fwd_ret: number
  p75_fwd_ret: number
  mean_mae_atr: number
  mean_mfe_atr: number
  mean_abs_move_in_atr: number
  state: string
  verdict: string
}

export interface CopilotBaseRate {
  instrument: string
  timeframe: string
  conditions: string[]
  n_occurrences: number
  history_span: [string, string]
  state: string
  caveat: string
  by_horizon: Record<string, CopilotHorizonOutcome>
}

export interface CopilotSkillReport {
  state: string
  n_resolved: number
  note?: string
}

export interface IntradayCopilotResponse {
  state: 'AVAILABLE' | 'NOT_COMPUTED'
  reason?: string
  generated_at: string
  schema_version?: string
  n_setups_logged?: number
  universe_scan_15m?: CopilotUniverseScan
  universe_scan_1h?: CopilotUniverseScan
  sample_base_rates?: Record<string, CopilotBaseRate>
  skill_report_all?: CopilotSkillReport
  design_note?: Record<string, unknown>
  safety_barrier: SafetyBarrier
}
