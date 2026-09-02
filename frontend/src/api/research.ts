import { apiGet, apiPost } from './client'
import type {
  BacktestRunRequest,
  BacktestRunResponse,
  ResearchAuditRequest,
  ResearchAuditResponse,
  StrategyLabResponse,
} from '../types/research'

/**
 * GET /api/research/strategy — read-only research configuration surface:
 * registered strategies, frozen research-spec defaults, backtester defaults,
 * supported symbol/timeframe universe, and backtest methodology.
 */
export function getStrategyLab(signal?: AbortSignal): Promise<StrategyLabResponse> {
  return apiGet<StrategyLabResponse>('/api/research/strategy', { signal })
}

/**
 * POST /api/research/backtest — runs ONE authoritative research backtest
 * (standard or walk-forward) and returns the serialized result. Research-only:
 * transmits no orders, touches no broker, schedules nothing. Fires only on an
 * explicit "Run Backtest" action.
 */
export function postBacktestRun(
  req: BacktestRunRequest,
  signal?: AbortSignal,
): Promise<BacktestRunResponse> {
  return apiPost<BacktestRunResponse>('/api/research/backtest', req, { signal })
}

/**
 * POST /api/research/audit — runs ONE authoritative backtest then applies the
 * canonical research_analytics / research_engine adversarial-audit functions
 * (R-multiples, 3-layer expectancy, bootstrap CI, scorecard, execution stress,
 * drift, dimension attribution). Research-only. Explicit action only.
 */
export function postResearchAudit(
  req: ResearchAuditRequest,
  signal?: AbortSignal,
): Promise<ResearchAuditResponse> {
  return apiPost<ResearchAuditResponse>('/api/research/audit', req, { signal })
}
