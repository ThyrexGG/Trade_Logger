/**
 * Crypto funding-carry edge — Phases 96 (edge test), 97 (portfolio construction
 * / sizing) and 98 (weekly forward evidence). Read-only research artifacts.
 */
import type { SafetyBarrier } from './strategyResearch'

type ResearchState = 'AVAILABLE' | 'NOT_COMPUTED'

export interface CarryLegMetrics {
  ann_funding: number
  ann_basis: number
  ann_cost: number
  ann_return: number
  ann_vol: number
  sharpe: number | null
  cumulative_return: number
  n_weeks: number
  positive_weeks_pct: number
  best_week: number
  worst_week: number
  start: string
  end: string
  state: string
}

export interface ForwardLedger {
  go_live_anchor: string
  data_through: string
  backtest_reference: CarryLegMetrics
  forward_evidence: CarryLegMetrics
  recommended_book_forward: {
    carry_fraction: number
    cash_rate: number
    cumulative_return: number
    n_weeks: number
  }
}

export interface ForwardSnapshot {
  captured_at: string
  data_through: string
  forward_weeks: number
  snapshot_key: string
  verdict: string
}

export interface CarryForwardResponse {
  state: ResearchState
  reason?: string
  verdict?: string
  verdict_reason?: string
  generated_at: string
  ledger?: ForwardLedger
  snapshot_history?: ForwardSnapshot[]
  design_note?: {
    go_live_anchor: string
    purpose: string
    rules: string
    verdict_gates: {
      insufficient_below_weeks: number
      confirm_at_weeks: number
      tracking_needs: string
      diverging_if: string
    }
  }
  safety_barrier: SafetyBarrier
}

export interface RecommendedBook {
  allocation: { cash: number; funding_carry: number; no_diversifier: number }
  cash_rate_assumed: number
  historical_metrics_no_tail: {
    cagr: number
    excess_cagr_over_cash: number
    ann_vol: number
    sharpe: number
    max_drawdown: number
    total_return: number
  }
}

export interface PortfolioConstructionResponse {
  state: ResearchState
  reason?: string
  usability_verdict?: string
  usability_reason?: string
  optimal_carry_fraction?: {
    by_fraction: Record<
      string,
      {
        mean_cagr: number
        median_cagr: number
        p05_cagr: number
        median_max_drawdown: number
        p05_max_drawdown: number
        prob_loss: number
        prob_ruin: number
        single_venue_loss_of_book: number
        worst_early_loss: number
      }
    >
  }
  recommended_book?: RecommendedBook
  fx_carry_status?: string
  generated_at: string
  safety_barrier: SafetyBarrier
}

export interface CarryHalfMetrics {
  cagr: number
  sharpe: number
  ann_vol: number
  max_drawdown: number
  positive_years: number
  n_years: number
  per_year_return: Record<string, number>
  start: string
  end: string
}

export interface FundingCarryResponse {
  state: ResearchState
  reason?: string
  edge_verdict?: string
  edge_reason?: string
  overall_verdict?: string
  headline_base?: CarryHalfMetrics & { calmar: number; avg_n_positions: number; avg_capital_deployed: number }
  headline_adverse?: CarryHalfMetrics
  halves?: { first_half: CarryHalfMetrics; second_half: CarryHalfMetrics }
  controls?: {
    funding_persistence?: { pooled_corr: number; median_per_coin: number; n_coin_positive: number }
    delta_neutrality_check?: {
      btc?: { beta: number; corr: number }
      crypto_basket?: { beta: number; corr: number }
      interpretation?: string
    }
    random_eligibility_placebo?: {
      real_sharpe: number
      placebo_p95_sharpe: number
      real_percentile: number
      empirical_p_one_sided: number
    }
    cost_ladder?: Record<string, { cagr: number; sharpe: number }>
    basis_attribution?: { ann_funding: number; ann_basis: number; ann_cost: number; funding_share_of_gross: number }
  }
  per_coin_breakdown?: unknown
  generated_at: string
  safety_barrier: SafetyBarrier
}
