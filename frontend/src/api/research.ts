import { apiGet, apiPost } from './client'
import type {
  BacktestRunRequest,
  BacktestRunResponse,
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
