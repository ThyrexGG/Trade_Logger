import { apiGet } from './client'
import type {
  AssetProfile,
  EconomicHeatmapResponse,
  IntelligenceSummary,
  OpportunityMapResponse,
} from '../types/intelligence'

/** GET /api/intelligence/summary — executive market state. */
export function getIntelligenceSummary(
  signal?: AbortSignal,
): Promise<IntelligenceSummary> {
  return apiGet<IntelligenceSummary>('/api/intelligence/summary', { signal })
}

/** GET /api/intelligence/opportunity-map — full ranked instrument universe. */
export function getOpportunityMap(
  signal?: AbortSignal,
): Promise<OpportunityMapResponse> {
  return apiGet<OpportunityMapResponse>('/api/intelligence/opportunity-map', {
    signal,
  })
}

/** GET /api/intelligence/asset-profile/{symbol} — deep contextual profile. */
export function getAssetProfile(
  symbol: string,
  signal?: AbortSignal,
): Promise<AssetProfile> {
  return apiGet<AssetProfile>(
    `/api/intelligence/asset-profile/${encodeURIComponent(symbol)}`,
    { signal },
  )
}

/** GET /api/intelligence/heatmap — economy × category macro matrix. */
export function getEconomicHeatmap(
  signal?: AbortSignal,
): Promise<EconomicHeatmapResponse> {
  return apiGet<EconomicHeatmapResponse>('/api/intelligence/heatmap', { signal })
}
