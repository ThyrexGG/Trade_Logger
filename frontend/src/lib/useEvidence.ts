import { useCallback, useEffect, useRef, useState } from 'react'
import { getForwardEvidenceState } from '../api/evidence'
import type { ForwardEvidenceState } from '../types/evidence'
import type { LoadState } from './useWatchlist'

export interface EvidenceView {
  state: LoadState
  data: ForwardEvidenceState | null
  error: string | null
  /** Background refresh running over already-loaded data. */
  refreshing: boolean
  /** ISO timestamp of the last successful load, for a "fetched Xs ago" cue. */
  fetchedAt: string | null
  refetch: () => void
}

const REFRESH_MS = 60_000
/** Skip an automatic mount-fetch if the cache is younger than this. */
const MOUNT_REUSE_MS = 15_000

// One shared module-level snapshot. All four evidence routes read the same
// forward-evidence state endpoint, so navigating between them reuses this and
// never fans out into duplicate requests.
const shared: {
  data: ForwardEvidenceState | null
  error: string | null
  fetchedAt: number
} = { data: null, error: null, fetchedAt: 0 }

/**
 * Coordinated single-request hook for the forward-evidence state. Race-safe
 * (AbortController + request id), cached at module scope for instant route
 * switches, slow-polled (60s, paused while the tab is hidden). The whole fetch
 * routine lives inside the effect with `[nonce]`-only deps so it cannot spin.
 */
export function useEvidenceState(): EvidenceView {
  const [data, setData] = useState<ForwardEvidenceState | null>(shared.data)
  const [status, setStatus] = useState<LoadState>(shared.data ? 'ready' : 'loading')
  const [error, setError] = useState<string | null>(shared.error)
  const [fetchedAt, setFetchedAt] = useState<string | null>(
    shared.fetchedAt ? new Date(shared.fetchedAt).toISOString() : null,
  )
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const requestId = useRef(0)
  const inFlight = useRef<AbortController | null>(null)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let disposed = false

    const load = () => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      const id = ++requestId.current
      if (shared.data) setRefreshing(true)

      getForwardEvidenceState(controller.signal)
        .then((payload) => {
          if (disposed || id !== requestId.current) return
          shared.data = payload
          shared.error = null
          shared.fetchedAt = Date.now()
          setData(payload)
          setError(null)
          setStatus('ready')
          setFetchedAt(new Date(shared.fetchedAt).toISOString())
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted || disposed || id !== requestId.current) return
          const message = err instanceof Error ? err.message : 'Unknown error'
          shared.error = message
          setError(message)
          if (!shared.data) setStatus('error')
        })
        .finally(() => {
          if (!disposed && id === requestId.current) setRefreshing(false)
        })
    }

    const fresh = Date.now() - shared.fetchedAt < MOUNT_REUSE_MS
    if (nonce > 0 || !shared.data || !fresh) {
      load()
    }

    const timer = window.setInterval(() => {
      if (!document.hidden) load()
    }, REFRESH_MS)
    const onVisible = () => {
      if (!document.hidden && Date.now() - shared.fetchedAt > MOUNT_REUSE_MS) load()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      disposed = true
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      inFlight.current?.abort()
    }
  }, [nonce])

  return { state: status, data, error, refreshing, fetchedAt, refetch }
}
