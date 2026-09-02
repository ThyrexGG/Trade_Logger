import { apiGet } from './client'
import type {
  AuditResponse,
  JournalResponse,
  OperationsSystemResponse,
} from '../types/operations'

/** GET /api/operations/journal — read-only closed-trade journal. */
export function getJournal(signal?: AbortSignal): Promise<JournalResponse> {
  return apiGet<JournalResponse>('/api/operations/journal', { signal })
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
