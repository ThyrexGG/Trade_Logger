import { apiGet, apiPut } from './client'

export interface MarketDataToggleResponse {
  live_market_data_enabled: boolean
  description: string
  generated_at: string
  safety_barrier: { live_automation_enabled: boolean; live_broker_transmission: string }
}

/** GET /api/system/market-data — current state of the live-MT5 quote switch. */
export function getMarketDataToggle(signal?: AbortSignal): Promise<MarketDataToggleResponse> {
  return apiGet<MarketDataToggleResponse>('/api/system/market-data', { signal })
}

/**
 * PUT /api/system/market-data — enable/disable live MT5 market data. When
 * disabled, the app never auto-launches the MetaTrader 5 terminal; quotes
 * come from Binance / Yahoo / cache instead.
 */
export function setMarketDataToggle(
  enabled: boolean,
  signal?: AbortSignal,
): Promise<MarketDataToggleResponse> {
  return apiPut<MarketDataToggleResponse>('/api/system/market-data', { enabled }, { signal })
}
