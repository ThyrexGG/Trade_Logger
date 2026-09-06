import { useCallback, useEffect, useRef, useState } from 'react'
import { getMarketDataToggle, setMarketDataToggle } from '../api/system'

interface UseMarketDataToggleResult {
  /** null while the first read is in flight */
  enabled: boolean | null
  busy: boolean
  error: string | null
  toggle: () => void
  setEnabled: (value: boolean) => void
}

/**
 * Reads and controls the live-MT5 market-data switch
 * (GET/PUT /api/system/market-data). When disabled, the backend never
 * auto-launches the MetaTrader 5 terminal; quotes fall back to
 * Binance / Yahoo / cache.
 */
export function useMarketDataToggle(): UseMarketDataToggleResult {
  const [enabled, setEnabledState] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getMarketDataToggle(controller.signal)
      .then((r) => setEnabledState(r.live_market_data_enabled))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Unknown error')
      })
    return () => controller.abort()
  }, [])

  const setEnabled = useCallback((value: boolean) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setBusy(true)
    setError(null)
    setMarketDataToggle(value, controller.signal)
      .then((r) => setEnabledState(r.live_market_data_enabled))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Unknown error')
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false)
      })
  }, [])

  const toggle = useCallback(() => {
    if (enabled === null) return
    setEnabled(!enabled)
  }, [enabled, setEnabled])

  return { enabled, busy, error, toggle, setEnabled }
}
