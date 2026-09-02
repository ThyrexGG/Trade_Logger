import { useCallback, useEffect, useRef, useState } from 'react'
import { getPositions } from '../api/positions'
import type { PositionsResponse } from '../types/positions'
import type { LoadState } from './useWatchlist'

interface UseOpenPositionsResult {
  state: LoadState
  data: PositionsResponse | null
  error: string | null
  refetch: () => void
}

const REFRESH_MS = 30_000

/** Read-only open positions for exposure context. One request, slow refresh. */
export function useOpenPositions(): UseOpenPositionsResult {
  const [state, setState] = useState<LoadState>('loading')
  const [data, setData] = useState<PositionsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const inFlight = useRef<AbortController | null>(null)
  const hasData = useRef(false)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    const load = () => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      getPositions(controller.signal)
        .then((payload) => {
          if (controller.signal.aborted) return
          setData(payload)
          setError(null)
          setState('ready')
          hasData.current = true
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          setError(err instanceof Error ? err.message : 'Unknown error')
          if (!hasData.current) setState('error')
        })
    }

    load()
    const timer = window.setInterval(() => {
      if (!document.hidden) load()
    }, REFRESH_MS)
    return () => {
      window.clearInterval(timer)
      inFlight.current?.abort()
    }
  }, [nonce])

  return { state, data, error, refetch }
}
