import { apiGet } from './client'
import type {
  MacroAssetsResponse,
  MacroCurrenciesResponse,
  MacroEventsResponse,
  MacroOverviewResponse,
  MacroSurprisesResponse,
} from '../types/macro'

export function getMacroOverview(signal?: AbortSignal): Promise<MacroOverviewResponse> {
  return apiGet<MacroOverviewResponse>('/api/macro/overview', { signal })
}

export function getMacroEvents(
  params: { window?: string; currency?: string; country?: string; impact?: string; indicator?: string; limit?: number } = {},
  signal?: AbortSignal,
): Promise<MacroEventsResponse> {
  const p = new URLSearchParams()
  if (params.window) p.set('window', params.window)
  if (params.currency) p.set('currency', params.currency)
  if (params.country) p.set('country', params.country)
  if (params.impact) p.set('impact', params.impact)
  if (params.indicator) p.set('indicator', params.indicator)
  if (params.limit != null) p.set('limit', String(params.limit))
  const qs = p.toString()
  return apiGet<MacroEventsResponse>(`/api/macro/events${qs ? `?${qs}` : ''}`, { signal })
}

export function getMacroCurrencies(signal?: AbortSignal): Promise<MacroCurrenciesResponse> {
  return apiGet<MacroCurrenciesResponse>('/api/macro/currencies', { signal })
}

export function getMacroAssets(signal?: AbortSignal): Promise<MacroAssetsResponse> {
  return apiGet<MacroAssetsResponse>('/api/macro/assets', { signal })
}

export function getMacroSurprises(signal?: AbortSignal): Promise<MacroSurprisesResponse> {
  return apiGet<MacroSurprisesResponse>('/api/macro/surprises', { signal })
}

export function getMacroScorecard(instrument: string, signal?: AbortSignal) {
  return apiGet<import('../types/macro').MacroScorecardResponse>(
    `/api/macro/scorecard/${encodeURIComponent(instrument)}`,
    { signal },
  )
}

export function getMacroScorecardHistory(instrument: string, limit = 90, signal?: AbortSignal) {
  return apiGet<import('../types/macro').MacroScorecardHistoryResponse>(
    `/api/macro/scorecard/${encodeURIComponent(instrument)}/history?limit=${limit}`,
    { signal },
  )
}

export function getMacroHeatmap(country: string, signal?: AbortSignal) {
  return apiGet<import('../types/macro').MacroHeatmapResponse>(
    `/api/macro/heatmap/${encodeURIComponent(country)}`,
    { signal },
  )
}

export function getMacroHeatmapIndex(signal?: AbortSignal) {
  return apiGet<import('../types/macro').MacroHeatmapIndexResponse>('/api/macro/heatmap', { signal })
}
