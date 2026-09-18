import { useCallback, useEffect, useRef, useState } from 'react'
import { AppState } from 'react-native'
import { getHealth } from './api/health'
import { HEALTH_POLL_MS } from './config'
import type { HealthResponse } from './types/health'

export type HealthState = 'checking' | 'connected' | 'unreachable'

interface UseApiHealth {
  state: HealthState
  health: HealthResponse | null
  /** how long the last check took, in ms */
  latencyMs: number | null
  recheck: () => void
}

/**
 * Polls GET /api/health. Pauses while the app is in the background (no point
 * burning battery/data) and rechecks the moment it returns to the foreground.
 */
export function useApiHealth(): UseApiHealth {
  const [state, setState] = useState<HealthState>('checking')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  const check = useCallback(() => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    const started = Date.now()
    getHealth(controller.signal)
      .then((h) => {
        if (inFlight.current !== controller) return
        setHealth(h)
        setState('connected')
        setLatencyMs(Date.now() - started)
      })
      .catch(() => {
        if (inFlight.current !== controller) return
        setState('unreachable')
        setLatencyMs(Date.now() - started)
      })
  }, [])

  useEffect(() => {
    check()
    let timer: ReturnType<typeof setInterval> | undefined = setInterval(check, HEALTH_POLL_MS)
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') {
        check()
        if (!timer) timer = setInterval(check, HEALTH_POLL_MS)
      } else if (timer) {
        clearInterval(timer)
        timer = undefined
      }
    })
    return () => {
      sub.remove()
      if (timer) clearInterval(timer)
      inFlight.current?.abort()
    }
  }, [check])

  return { state, health, latencyMs, recheck: check }
}
