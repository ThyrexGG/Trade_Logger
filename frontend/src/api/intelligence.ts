import { apiGet } from './client'
import type {
  AssetIntelligence,
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

/**
 * GET /api/intelligence/asset/{asset} — the canonical Phase-67 evidence fusion
 * snapshot. `asOf` (ISO-8601 UTC) requests a reproducible historical snapshot;
 * omit it for a live one.
 */
export function getAssetIntelligence(
  asset: string,
  opts: { asOf?: string; timeframe?: string; signal?: AbortSignal } = {},
): Promise<AssetIntelligence> {
  const params = new URLSearchParams()
  if (opts.asOf) params.set('as_of', opts.asOf)
  if (opts.timeframe) params.set('timeframe', opts.timeframe)
  const qs = params.toString()
  return apiGet<AssetIntelligence>(
    `/api/intelligence/asset/${encodeURIComponent(asset)}${qs ? `?${qs}` : ''}`,
    { signal: opts.signal },
  )
}

/** GET /api/intelligence/heatmap — economy × category macro matrix. */
export function getEconomicHeatmap(
  signal?: AbortSignal,
): Promise<EconomicHeatmapResponse> {
  return apiGet<EconomicHeatmapResponse>('/api/intelligence/heatmap', { signal })
}
