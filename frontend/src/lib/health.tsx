import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { getHealth } from '../api/health'
import type { HealthResponse } from '../types/health'

export type ConnectionState = 'loading' | 'connected' | 'error'

interface HealthContextValue {
  state: ConnectionState
  data: HealthResponse | null
  error: string | null
  lastChecked: Date | null
  refetch: () => void
}

const HealthContext = createContext<HealthContextValue | null>(null)

const POLL_INTERVAL_MS = 30_000

/**
 * Polls /api/health on a slow interval and shares the result app-wide.
 *
 * Non-blocking by design: the shell renders immediately and navigation never
 * waits on this. Polling pauses while the tab is hidden to avoid idle backend
 * traffic, and resumes with an immediate check when the tab is focused again.
 */
export function HealthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConnectionState>('loading')
  const [data, setData] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  const check = useCallback(() => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller

    getHealth(controller.signal)
      .then((payload) => {
        if (controller.signal.aborted) return
        setData(payload)
        setError(null)
        setState('connected')
        setLastChecked(new Date())
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setData(null)
        setError(err instanceof Error ? err.message : 'Unknown error')
        setState('error')
        setLastChecked(new Date())
      })
  }, [])

  useEffect(() => {
    check()

    let timer: number | undefined
    const start = () => {
      window.clearInterval(timer)
      timer = window.setInterval(() => {
        if (!document.hidden) check()
      }, POLL_INTERVAL_MS)
    }
    const onVisibility = () => {
      if (!document.hidden) check()
    }

    start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
      inFlight.current?.abort()
    }
  }, [check])

  return (
    <HealthContext.Provider
      value={{ state, data, error, lastChecked, refetch: check }}
    >
      {children}
    </HealthContext.Provider>
  )
}

export function useHealth(): HealthContextValue {
  const ctx = useContext(HealthContext)
  if (!ctx) {
    throw new Error('useHealth must be used within <HealthProvider>')
  }
  return ctx
}
