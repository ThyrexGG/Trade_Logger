import { useCallback, useEffect, useRef, useState } from 'react'
import { getCandles } from '../api/market'
import type { CandlesResponse } from '../types/market'

export const CHART_TIMEFRAMES = ['15m', '1h', '4h', '1d'] as const
export type ChartTimeframe = (typeof CHART_TIMEFRAMES)[number]

/** Poll cadence by feed liveness — a real-time feed refreshes fast, a polled
 *  (delayed) one slowly to stay well under the upstream's rate limits. */
const POLL_MS: Record<string, number> = {
  live: 6_000,
  delayed: 30_000,
  synthetic: 60_000,
  unknown: 30_000,
}

interface State {
  data: CandlesResponse | null
  loading: boolean
  error: string | null
}

/**
 * Candle data for the live chart: fetch on symbol/tf change, then keep it fresh
 * on an interval whose length depends on the source (`live` vs `delayed`).
 * Race-safe; pauses while the tab is hidden.
 */
export function usePriceChart(symbol: string | null, tf: ChartTimeframe, count = 200) {
  const [state, setState] = useState<State>({ data: null, loading: false, error: null })
  const reqId = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  const load = useCallback(
    async (isRefresh: boolean) => {
      if (!symbol) return
      const id = ++reqId.current
      if (!isRefresh) setState((s) => ({ ...s, loading: true, error: null }))
      try {
        const r = await getCandles(symbol, tf, count)
        if (id !== reqId.current) return
        setState({ data: r, loading: false, error: null })
      } catch (e) {
        if (id !== reqId.current) return
        setState((s) => ({
          data: s.data,
          loading: false,
          error: e instanceof Error ? e.message : 'Failed to load candles',
        }))
      }
    },
    [symbol, tf, count],
  )

  useEffect(() => {
    reqId.current++
    setState({ data: null, loading: !!symbol, error: null })
    if (!symbol) return
    void load(false)

    let cancelled = false
    const schedule = () => {
      if (cancelled) return
      if (timer.current) clearTimeout(timer.current)
      const liveness = stateRef.current.data?.liveness ?? 'unknown'
      const ms = POLL_MS[liveness] ?? POLL_MS.unknown
      timer.current = setTimeout(async () => {
        if (!document.hidden) await load(true)
        schedule()
      }, ms)
    }
    schedule()

    return () => {
      cancelled = true
      if (timer.current) clearTimeout(timer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, tf, count])

  return { ...state, refetch: () => load(true) }
}
