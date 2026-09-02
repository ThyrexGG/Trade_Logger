import { useCallback, useEffect, useRef, useState } from 'react'
import { getStrategyLab } from '../api/research'
import type { StrategyLabResponse } from '../types/research'
import type { LoadState } from './useWatchlist'

interface UseStrategyLabResult {
  state: LoadState
  data: StrategyLabResponse | null
  error: string | null
  refetch: () => void
}

// The research configuration surface is effectively static for a session, so it
// is fetched once and cached at module scope. No polling.
let cache: StrategyLabResponse | null = null

/** One GET for the read-only Strategy Lab configuration. Cached, race-safe. */
export function useStrategyLab(): UseStrategyLabResult {
  const [data, setData] = useState<StrategyLabResponse | null>(cache)
  const [state, setState] = useState<LoadState>(cache ? 'ready' : 'loading')
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const requestId = useRef(0)

  const refetch = useCallback(() => {
    cache = null
    setNonce((n) => n + 1)
  }, [])

  useEffect(() => {
    if (cache && nonce === 0) return
    const controller = new AbortController()
    const id = ++requestId.current
    setState((s) => (data ? s : 'loading'))
    setError(null)

    getStrategyLab(controller.signal)
      .then((payload) => {
        if (id !== requestId.current) return
        cache = payload
        setData(payload)
        setState('ready')
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || id !== requestId.current) return
        setError(err instanceof Error ? err.message : 'Unknown error')
        if (!cache) setState('error')
      })

    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce])

  return { state, data, error, refetch }
}
