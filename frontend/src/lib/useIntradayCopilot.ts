import { useEffect, useRef, useState } from 'react'
import { getIntradayCopilot } from '../api/intradayCopilot'
import type { IntradayCopilotResponse } from '../types/intradayCopilot'
import type { LoadState } from './useWatchlist'

// Module-level cache — the Phase 100 artifact is a persisted daily scan, so
// every consumer on the page shares one fetch for the session.
let cached: IntradayCopilotResponse | null = null

/**
 * Reads the Phase 100 intraday co-pilot artifact once and shares it. Read-only,
 * no polling — the artifact only changes when `python -m phase100_intraday_copilot`
 * re-runs.
 */
export function useIntradayCopilot() {
  const [data, setData] = useState<IntradayCopilotResponse | null>(cached)
  const [state, setState] = useState<LoadState>(cached ? 'ready' : 'loading')
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    if (cached || started.current) return
    started.current = true
    const controller = new AbortController()
    getIntradayCopilot(controller.signal)
      .then((r) => {
        cached = r
        setData(r)
        setState('ready')
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Failed to load the intraday co-pilot')
        setState('error')
      })
    return () => controller.abort()
  }, [])

  return { data, state, error }
}
