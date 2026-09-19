import type { AnalyticsDayTradesResponse, AnalyticsPerformanceResponse, AnalyticsQuery } from '../types/analytics'
import { apiGet, apiPost } from './client'

/** GET /api/analytics/performance — account / date filtered performance. */
export function getAnalyticsPerformance(query: AnalyticsQuery, signal?: AbortSignal): Promise<AnalyticsPerformanceResponse> {
  const p = new URLSearchParams()
  if (query.account && query.account !== 'ALL') p.set('account', query.account)
  if (query.symbols?.length) p.set('symbols', query.symbols.join(','))
  if (query.start) p.set('start', query.start)
  if (query.end) p.set('end', query.end)
  if (query.initial_balance != null) p.set('initial_balance', String(query.initial_balance))
  const qs = p.toString()
  return apiGet<AnalyticsPerformanceResponse>(`/api/analytics/performance${qs ? `?${qs}` : ''}`, signal)
}

/** POST /api/analytics/initial-balance — remember a starting balance for one account. */
export function saveInitialBalance(account: string, value: number): Promise<{ account: string; initial_balance: number }> {
  const p = new URLSearchParams({ account, value: String(value) })
  return apiPost(`/api/analytics/initial-balance?${p.toString()}`, {})
}

/** GET /api/analytics/day — the closed trades of one calendar day (calendar drill-down). */
export function getDayTrades(date: string, account?: string, signal?: AbortSignal): Promise<AnalyticsDayTradesResponse> {
  const p = new URLSearchParams({ date })
  if (account && account !== 'ALL') p.set('account', account)
  return apiGet<AnalyticsDayTradesResponse>(`/api/analytics/day?${p.toString()}`, signal)
}
