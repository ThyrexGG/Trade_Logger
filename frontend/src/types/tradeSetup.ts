/** Phase 72 — Trade Setup Engine. */
import type { SafetyBarrier } from './strategyResearch'

export type SetupState =
  | 'NO_SETUP'
  | 'WATCH'
  | 'SETUP_FORMING'
  | 'READY'
  | 'INVALIDATED'
  | 'STALE'
  | 'INSUFFICIENT_EVIDENCE'

export interface SetupCondition {
  name: string
  mandatory: boolean
  passed: boolean | null
  detail: string
  evidence_ref: string | null
}

export interface TradeSetup {
  asset: string
  state: SetupState
  as_of: string
  generated_at: string
  mode: 'live' | 'historical'
  reason: string
  direction: 'LONG' | 'SHORT' | null
  strategy_id: string | null
  strategy_version: string | null
  strategy_family: string | null
  timeframe_stack: string | null
  session: string | null
  entry: number | null
  stop_loss: number | null
  take_profit: number | null
  risk_reward: number | null
  conditions: SetupCondition[]
  failing_conditions: string[]
  waiting_for: string | null
  strategy_validation: Record<string, unknown>
  evidence_provenance: string[]
  safety_barrier: SafetyBarrier
}

export interface TradeSetupListItem {
  asset: string
  state: SetupState
  direction: 'LONG' | 'SHORT' | null
  strategy_id: string | null
  waiting_for: string | null
  reason: string
  oos_expectancy_r: number | null
}

export interface TradeSetupListResponse {
  generated_at: string
  setups: TradeSetupListItem[]
  safety_barrier: SafetyBarrier
}
