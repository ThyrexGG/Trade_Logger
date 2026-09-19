import type { JournalResponse } from '../types/journal'
import { apiGet } from './client'

/** GET /api/operations/journal — every closed trade for the signed-in user. */
export function getJournal(signal?: AbortSignal): Promise<JournalResponse> {
  return apiGet<JournalResponse>('/api/operations/journal', signal)
}
