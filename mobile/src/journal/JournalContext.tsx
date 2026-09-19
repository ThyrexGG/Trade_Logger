import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { AppState } from 'react-native'
import { getJournal } from '../api/journal'
import type { JournalResponse, JournalTradeItem } from '../types/journal'

interface JournalValue {
  data: JournalResponse | null
  loading: boolean
  refreshing: boolean
  error: string | null
  refresh: () => Promise<void>
  /** Swap one edited trade into the cached list so screens update without a refetch (used by M5 editing). */
  applyEntry: (entry: JournalTradeItem) => void
}

const Ctx = createContext<JournalValue | null>(null)

export function useJournal(): JournalValue {
  const v = useContext(Ctx)
  if (!v) throw new Error('useJournal must be used inside <JournalProvider>')
  return v
}

/** Loads the closed-trade journal once, refreshes on demand and when the app returns to the foreground. */
export function JournalProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<JournalResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback(async (manual: boolean) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    if (manual) setRefreshing(true)
    try {
      const payload = await getJournal(controller.signal)
      if (controller.signal.aborted) return
      setData(payload)
      setError(null)
    } catch (err) {
      if (controller.signal.aborted) return
      setError(err instanceof Error ? err.message : 'Could not load the journal.')
    } finally {
      if (inFlight.current === controller) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    void load(false)
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') void load(false)
    })
    return () => {
      sub.remove()
      inFlight.current?.abort()
    }
  }, [load])

  const refresh = useCallback(() => load(true), [load])

  const applyEntry = useCallback((entry: JournalTradeItem) => {
    setData((prev) =>
      prev ? { ...prev, entries: prev.entries.map((e) => (e.trade_id === entry.trade_id ? { ...e, ...entry } : e)) } : prev,
    )
  }, [])

  const value = useMemo(
    () => ({ data, loading, refreshing, error, refresh, applyEntry }),
    [data, loading, refreshing, error, refresh, applyEntry],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
