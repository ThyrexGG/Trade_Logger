import { useCallback, useEffect, useRef, useState } from 'react'
import { postBacktestRun } from '../api/research'
import type { BacktestRunRequest, BacktestRunResponse } from '../types/research'

export type BacktestRunState = 'idle' | 'running' | 'complete' | 'failed'

interface UseBacktestRunResult {
  state: BacktestRunState
  result: BacktestRunResponse | null
  /** The exact request that produced `result` — used to detect stale config. */
  resultRequest: BacktestRunRequest | null
  error: string | null
  run: (req: BacktestRunRequest) => void
  reset: () => void
}

/**
 * Drives POST /api/research/backtest. Fires ONLY when `run()` is called (an
 * explicit "Run Backtest" action) — never on mount, re-render, tab switch or
 * StrictMode double-invoke. A previous result stays visible while a new run is
 * in flight; a failed run keeps the last good result and surfaces `error`.
 * Race-safe via AbortController + request id; the in-flight run is aborted on
 * unmount and whenever a new run starts.
 */
export function useBacktestRun(): UseBacktestRunResult {
  const [state, setState] = useState<BacktestRunState>('idle')
  const [result, setResult] = useState<BacktestRunResponse | null>(null)
  const [resultRequest, setResultRequest] = useState<BacktestRunRequest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)
  const requestId = useRef(0)

  useEffect(() => () => inFlight.current?.abort(), [])

  const run = useCallback((req: BacktestRunRequest) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    const id = ++requestId.current

    setState('running')
    setError(null)

    postBacktestRun(req, controller.signal)
      .then((payload) => {
        if (id !== requestId.current) return
        setResult(payload)
        setResultRequest(req)
        setState(payload.status === 'failed' ? 'failed' : 'complete')
        if (payload.status === 'failed') {
          setError(payload.error ?? 'The backtest engine reported a failure.')
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || id !== requestId.current) return
        setError(err instanceof Error ? err.message : 'Unknown error')
        setState('failed')
      })
  }, [])

  const reset = useCallback(() => {
    inFlight.current?.abort()
    requestId.current++
    setState('idle')
    setResult(null)
    setResultRequest(null)
    setError(null)
  }, [])

  return { state, result, resultRequest, error, run, reset }
}
