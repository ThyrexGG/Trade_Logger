import { apiGet, apiPost } from './client'
import type {
  AnalyticsDayTradesResponse,
  AnalyticsPerformanceResponse,
  AnalyticsQuery,
} from '../types/analytics'

/** GET /api/analytics/performance — account/symbol/date-filtered performance. */
export function getAnalyticsPerformance(
  query: AnalyticsQuery = {},
  signal?: AbortSignal,
): Promise<AnalyticsPerformanceResponse> {
  const p = new URLSearchParams()
  if (query.account && query.account !== 'ALL') p.set('account', query.account)
  if (query.symbols && query.symbols.length) p.set('symbols', query.symbols.join(','))
  if (query.start) p.set('start', query.start)
  if (query.end) p.set('end', query.end)
  if (query.initial_balance != null) p.set('initial_balance', String(query.initial_balance))
  const qs = p.toString()
  return apiGet<AnalyticsPerformanceResponse>(
    `/api/analytics/performance${qs ? `?${qs}` : ''}`,
    { signal },
  )
}

/** POST /api/analytics/initial-balance — remembers a starting balance for one
 * account so it survives a reload instead of resetting to the auto-guess. */
export function saveInitialBalance(account: string, value: number): Promise<{ account: string; initial_balance: number }> {
  const p = new URLSearchParams({ account, value: String(value) })
  return apiPost<{ account: string; initial_balance: number }>(`/api/analytics/initial-balance?${p.toString()}`, {})
}

/** GET /api/analytics/day — closed trades for one calendar day (calendar drill-down). */
export function getDayTrades(
  date: string,
  query: Pick<AnalyticsQuery, 'account' | 'symbols'> = {},
  signal?: AbortSignal,
): Promise<AnalyticsDayTradesResponse> {
  const p = new URLSearchParams({ date })
  if (query.account && query.account !== 'ALL') p.set('account', query.account)
  if (query.symbols && query.symbols.length) p.set('symbols', query.symbols.join(','))
  return apiGet<AnalyticsDayTradesResponse>(`/api/analytics/day?${p.toString()}`, { signal })
}
