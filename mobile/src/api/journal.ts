import type { JournalResponse, JournalUpdateRequest, JournalUpdateResponse } from '../types/journal'
import { apiGet, apiPatch } from './client'

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
