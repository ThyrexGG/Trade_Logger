import { apiGet, apiPatch } from './client'
import type {
  AuditResponse,
  JournalResponse,
  JournalUpdateRequest,
  JournalUpdateResponse,
  OperationsSystemResponse,
} from '../types/operations'

/** GET /api/operations/journal — read-only closed-trade journal. */
export function getJournal(signal?: AbortSignal): Promise<JournalResponse> {
  return apiGet<JournalResponse>('/api/operations/journal', { signal })
}

/**
 * PATCH /api/operations/journal/{trade_id} — update the subjective annotations
 * (setup_tag / notes / chart_snapshot_url) of one closed trade. Never touches
 * execution, orders or a broker.
 */
export function patchJournalEntry(
  tradeId: string,
  body: JournalUpdateRequest,
  signal?: AbortSignal,
): Promise<JournalUpdateResponse> {
  return apiPatch<JournalUpdateResponse>(
    `/api/operations/journal/${encodeURIComponent(tradeId)}`,
    body,
    { signal },
  )
}

/** GET /api/operations/audit — read-only execution audit trail. */
export function getAudit(
  limit = 200,
  signal?: AbortSignal,
): Promise<AuditResponse> {
  return apiGet<AuditResponse>(`/api/operations/audit?limit=${limit}`, { signal })
}

/** GET /api/operations/system — health values + safety-gate diagnostics. */
export function getSystemOps(
  signal?: AbortSignal,
): Promise<OperationsSystemResponse> {
  return apiGet<OperationsSystemResponse>('/api/operations/system', { signal })
}
