import { apiGet } from './client'
import type { TradeSetup, TradeSetupListResponse } from '../types/tradeSetup'

/** GET /api/trade-setup — compact state for every universe instrument. */
export function getTradeSetups(signal?: AbortSignal): Promise<TradeSetupListResponse> {
  return apiGet<TradeSetupListResponse>('/api/trade-setup', { signal })
}

/** GET /api/trade-setup/{asset} — full deterministic setup evaluation. */
export function getTradeSetup(asset: string, signal?: AbortSignal): Promise<TradeSetup> {
  return apiGet<TradeSetup>(`/api/trade-setup/${encodeURIComponent(asset)}`, { signal })
}
