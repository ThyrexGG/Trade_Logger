import { useCallback, useEffect, useRef, useState } from 'react'
import { postRiskPreview } from '../api/risk'
import type { RiskPreviewRequest, RiskPreviewResponse } from '../types/risk'

export type RiskState = 'idle' | 'calculating' | 'ready' | 'error'

interface UseRiskPreviewResult {
  state: RiskState
  result: RiskPreviewResponse | null
  /** The exact request that produced `result` — used to detect stale inputs. */
  resultRequest: RiskPreviewRequest | null
  error: string | null
  calculate: (req: RiskPreviewRequest) => void
  reset: () => void
}

/**
 * Drives POST /api/risk/preview. Fires only when `calculate()` is called
 * (explicit "Calculate Risk" action) — never on input change. The previous
 * result stays visible while a new one is calculating; a failed request keeps
 * the last good result and surfaces `error`.
 */
export function useRiskPreview(): UseRiskPreviewResult {
  const [state, setState] = useState<RiskState>('idle')
  const [result, setResult] = useState<RiskPreviewResponse | null>(null)
  const [resultRequest, setResultRequest] = useState<RiskPreviewRequest | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)
  const requestId = useRef(0)

  useEffect(() => () => inFlight.current?.abort(), [])

  const calculate = useCallback((req: RiskPreviewRequest) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    const id = ++requestId.current

    setState('calculating')
    setError(null)

    postRiskPreview(req, controller.signal)
      .then((payload) => {
        if (id !== requestId.current) return
        setResult(payload)
        setResultRequest(req)
        setState('ready')
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || id !== requestId.current) return
        setError(err instanceof Error ? err.message : 'Unknown error')
        setState('error')
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

  return { state, result, resultRequest, error, calculate, reset }
}
