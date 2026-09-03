import { apiGet } from './client'
import type {
  GoldBaselineResponse,
  HistoricalCoverageResponse,
  PairRankingResponse,
  StrategiesResponse,
} from '../types/strategyResearch'

/** GET /api/research/historical/coverage — persistent OHLCV store coverage + sufficiency. */
export function getHistoricalCoverage(signal?: AbortSignal): Promise<HistoricalCoverageResponse> {
  return apiGet<HistoricalCoverageResponse>('/api/research/historical/coverage', { signal })
}

/** GET /api/research/gold-baseline — recovered previous Gold discovery (read-only). */
export function getGoldBaseline(signal?: AbortSignal): Promise<GoldBaselineResponse> {
  return apiGet<GoldBaselineResponse>('/api/research/gold-baseline', { signal })
}

/** GET /api/research/strategies — machine-readable strategy definitions. */
export function getStrategies(signal?: AbortSignal): Promise<StrategiesResponse> {
  return apiGet<StrategiesResponse>('/api/research/strategies', { signal })
}

/** GET /api/research/pair-ranking — the persisted pair x strategy leaderboard artifact. */
export function getPairRanking(signal?: AbortSignal): Promise<PairRankingResponse> {
  return apiGet<PairRankingResponse>('/api/research/pair-ranking', { signal })
}
