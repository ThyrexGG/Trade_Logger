import { useCallback, useEffect, useRef, useState } from 'react'
import { getAudit, getJournal, getSystemOps } from '../api/operations'
import type {
  AuditResponse,
  JournalResponse,
  OperationsSystemResponse,
} from '../types/operations'
import type { LoadState } from './useWatchlist'

export interface OpsResource<T> {
  state: LoadState
  data: T | null
  error: string | null
  refreshing: boolean
  refetch: () => void
}

interface CacheSlot {
  data: unknown
  error: string | null
  at: number
}
// One shared slot per resource key. Lets the overview page and a sub-page reuse
// the same fetch instead of each firing its own, and makes route re-entry
// instant with a background refresh.
const cache = new Map<string, CacheSlot>()
/** A cached payload younger than this serves a mount without an immediate refetch. */
const MOUNT_REUSE_MS = 12_000

/**
 * Shared read-only operations resource: one GET, race-safe (AbortController),
 * module-cached, slow interval refresh paused while the tab is hidden, last-good
 * data kept during refresh and on error. The whole fetch routine lives inside a
 * `[nonce]`-only effect so it cannot spin.
 */
function useOpsResource<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  refreshMs: number,
): OpsResource<T> {
  const slot = cache.get(key)
  const [data, setData] = useState<T | null>((slot?.data as T) ?? null)
  const [state, setState] = useState<LoadState>(slot?.data ? 'ready' : 'loading')
  const [error, setError] = useState<string | null>(slot?.error ?? null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const hasData = useRef(Boolean(slot?.data))

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let disposed = false
    let controller: AbortController | null = null

    const load = () => {
      controller?.abort()
      controller = new AbortController()
      const signal = controller.signal
      if (hasData.current) setRefreshing(true)

      fetcher(signal)
        .then((payload) => {
          if (disposed || signal.aborted) return
          cache.set(key, { data: payload, error: null, at: Date.now() })
          setData(payload)
          setError(null)
          setState('ready')
          hasData.current = true
        })
        .catch((err: unknown) => {
          if (disposed || signal.aborted) return
          const message = err instanceof Error ? err.message : 'Unknown error'
          const prev = cache.get(key)
          cache.set(key, { data: prev?.data ?? null, error: message, at: Date.now() })
          setError(message)
          if (!hasData.current) setState('error')
        })
        .finally(() => {
          if (!disposed && !signal.aborted) setRefreshing(false)
        })
    }

    const cached = cache.get(key)
    const fresh = cached?.data && Date.now() - cached.at < MOUNT_REUSE_MS
    if (nonce > 0 || !fresh) load()

    const timer = window.setInterval(() => {
      if (!document.hidden) load()
    }, refreshMs)
    const onVisible = () => {
      const c = cache.get(key)
      if (!document.hidden && (!c || Date.now() - c.at > MOUNT_REUSE_MS)) load()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      disposed = true
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      controller?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce])

  return { state, data, error, refreshing, refetch }
}

/** Read-only trade journal (`closed_trades`). Slow refresh — journal changes rarely. */
export function useJournal(): OpsResource<JournalResponse> {
  return useOpsResource('journal', (s) => getJournal(s), 60_000)
}

/** Read-only execution audit trail (`execution_orders`). */
export function useAudit(): OpsResource<AuditResponse> {
  return useOpsResource('audit', (s) => getAudit(200, s), 60_000)
}

/** Operational system health + safety-gate diagnostics. Lightweight, faster refresh. */
export function useSystemOps(): OpsResource<OperationsSystemResponse> {
  return useOpsResource('system', (s) => getSystemOps(s), 20_000)
}
