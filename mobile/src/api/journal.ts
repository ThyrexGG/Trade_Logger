import type { JournalResponse, JournalTradeItem, JournalUpdateRequest, JournalUpdateResponse, ManualTradeRequest } from '../types/journal'
import { apiGet, apiPatch, apiPost } from './client'

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

export interface JournalTagStat {
  tag: string
  n: number
  wins: number
  win_rate: number | null
  net_total: number
  expectancy: number | null
}

/** GET /api/operations/journal/tag-stats — realised record per setup tag. */
export function getJournalTagStats(signal?: AbortSignal): Promise<{ tags: JournalTagStat[]; timestamp: string }> {
  return apiGet<{ tags: JournalTagStat[]; timestamp: string }>('/api/operations/journal/tag-stats', signal)
}
