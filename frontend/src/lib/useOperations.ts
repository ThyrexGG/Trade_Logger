import { useCallback } from 'react'
import { getAudit, getJournal, getSystemOps } from '../api/operations'
import type {
  AuditResponse,
  JournalResponse,
  JournalTradeItem,
  OperationsSystemResponse,
} from '../types/operations'
import { useCachedResource, type CachedResource } from './dataCache'

export type OpsResource<T> = CachedResource<T>

/** Read-only operations resource, cached + revalidated in the background —
 * see `useCachedResource`. Reused by the overview page and any sub-page so
 * they share one fetch and route re-entry is instant. */
function useOpsResource<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  refreshMs: number,
): OpsResource<T> {
  // A broker catch-up sync just landed new rows — pull them in now rather
  // than waiting for the slow interval.
  return useCachedResource(key, fetcher, { refreshMs, revalidateOn: ['tl:synced'] })
}

export interface JournalResource extends OpsResource<JournalResponse> {
  /** Splice an authoritative updated entry (from a PATCH response) into the list. */
  applyEntry: (entry: JournalTradeItem) => void
}

/** Trade journal (`closed_trades`). Slow refresh — journal changes rarely.
 *  Annotation fields (setup_tag / notes / chart_snapshot_url) are editable via PATCH. */
export function useJournal(): JournalResource {
  const base = useOpsResource('journal', (s) => getJournal(s), 60_000)
  const applyEntry = useCallback(
    (entry: JournalTradeItem) => {
      base.setLocal((prev) =>
        prev
          ? {
              ...prev,
              entries: prev.entries.map((e) => (e.trade_id === entry.trade_id ? entry : e)),
              timestamp: new Date().toISOString(),
            }
          : prev,
      )
    },
    [base],
  )
  return { ...base, applyEntry }
}

/** Read-only execution audit trail (`execution_orders`). */
export function useAudit(): OpsResource<AuditResponse> {
  return useOpsResource('audit', (s) => getAudit(200, s), 60_000)
}

/** Operational system health + safety-gate diagnostics. Lightweight, faster refresh. */
export function useSystemOps(): OpsResource<OperationsSystemResponse> {
  return useOpsResource('system', (s) => getSystemOps(s), 20_000)
}
