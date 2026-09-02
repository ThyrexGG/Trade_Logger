import { useCallback, useEffect, useRef, useState } from 'react'
import { postResearchAudit } from '../api/research'
import type { ResearchAuditRequest, ResearchAuditResponse } from '../types/research'

export type ResearchAuditState = 'idle' | 'running' | 'complete' | 'failed'

interface UseResearchAuditResult {
  state: ResearchAuditState
  result: ResearchAuditResponse | null
  resultRequest: ResearchAuditRequest | null
  error: string | null
  run: (req: ResearchAuditRequest) => void
  reset: () => void
}

/**
 * Drives POST /api/research/audit. Fires ONLY on an explicit run() call —
 * never on mount, re-render, tab switch or StrictMode double-invoke. Previous
 * result stays visible while a new run is in flight; a failed run keeps the
 * last good result. Race-safe via AbortController + request id.
 */
export function useResearchAudit(): UseResearchAuditResult {
  const [state, setState] = useState<ResearchAuditState>('idle')
  const [result, setResult] = useState<ResearchAuditResponse | null>(null)
  const [resultRequest, setResultRequest] = useState<ResearchAuditRequest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)
  const requestId = useRef(0)

  useEffect(() => () => inFlight.current?.abort(), [])

  const run = useCallback((req: ResearchAuditRequest) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    const id = ++requestId.current
    setState('running')
    setError(null)

    postResearchAudit(req, controller.signal)
      .then((payload) => {
        if (id !== requestId.current) return
        setResult(payload)
        setResultRequest(req)
        setState(payload.status === 'failed' ? 'failed' : 'complete')
        if (payload.status === 'failed') {
          setError(payload.error ?? 'The research engine reported a failure.')
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
