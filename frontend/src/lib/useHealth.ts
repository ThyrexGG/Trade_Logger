import { useCallback, useEffect, useState } from 'react'
import { getHealth } from '../api/health'
import type { HealthResponse } from '../types/health'

export type ConnectionState = 'loading' | 'connected' | 'error'

interface UseHealthResult {
  state: ConnectionState
  data: HealthResponse | null
  error: string | null
  refetch: () => void
}

/** Fetches /api/health once on mount and exposes loading / connected / error states. */
export function useHealth(): UseHealthResult {
  const [state, setState] = useState<ConnectionState>('loading')
  const [data, setData] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    setState('loading')
    setError(null)

    getHealth(controller.signal)
      .then((payload) => {
        setData(payload)
        setState('connected')
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setData(null)
        setError(err instanceof Error ? err.message : 'Unknown error')
        setState('error')
      })

    return () => controller.abort()
  }, [nonce])

  return { state, data, error, refetch }
}
