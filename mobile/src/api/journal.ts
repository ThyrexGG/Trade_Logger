import type { JournalResponse, JournalTradeItem, JournalUpdateRequest, JournalUpdateResponse, ManualTradeRequest } from '../types/journal'
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client'

/** GET /api/operations/journal — every closed trade for the signed-in user. */
export function getJournal(signal?: AbortSignal): Promise<JournalResponse> {
  return apiGet<JournalResponse>('/api/operations/journal', signal)
}

/** PATCH /api/operations/journal/{trade_id} — edit notes / tag / chart link / rating of a closed trade. */
export function patchJournalEntry(
  tradeId: string,
  body: JournalUpdateRequest,
  signal?: AbortSignal,
): Promise<JournalUpdateResponse> {
  return apiPatch<JournalUpdateResponse>(`/api/operations/journal/${encodeURIComponent(tradeId)}`, body, signal)
}

/** POST /api/operations/journal/trades — record a trade that never went through a broker sync. */
export function createManualTrade(body: ManualTradeRequest, signal?: AbortSignal): Promise<JournalTradeItem> {
  return apiPost<JournalTradeItem>('/api/operations/journal/trades', body, signal)
}

/** PUT /api/operations/journal/trades/{id} — correct a trade you logged by hand (broker-synced trades are refused). */
export function updateManualTrade(tradeId: string, body: ManualTradeRequest, signal?: AbortSignal): Promise<JournalTradeItem> {
  return apiPut<JournalTradeItem>(`/api/operations/journal/trades/${encodeURIComponent(tradeId)}`, body, signal)
}

/** DELETE /api/operations/journal/trades/{id} — remove a trade you logged by hand, with its screenshots. */
export function deleteManualTrade(tradeId: string, signal?: AbortSignal): Promise<{ deleted: boolean; trade_id: string }> {
  return apiDelete<{ deleted: boolean; trade_id: string }>(`/api/operations/journal/trades/${encodeURIComponent(tradeId)}`, signal)
}

export interface JournalTagStat {
  tag: string
  n: number
  wins: number
  win_rate: number | null
  net_total: number
  expectancy: number | null
}

export interface JournalTagStats {
  tags: JournalTagStat[]
  /** closed trades that have no setup tag, and what they made in total */
  untagged: { n: number; net_total: number }
  total_trades: number
  timestamp: string
}

/** GET /api/operations/journal/tag-stats — realised record per setup tag, and how many trades have none. */
export function getJournalTagStats(signal?: AbortSignal): Promise<JournalTagStats> {
  return apiGet<JournalTagStats>('/api/operations/journal/tag-stats', signal)
}
