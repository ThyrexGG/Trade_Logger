import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { runSyncIfStale } from '../api/system'

/**
 * Fires one broker sync when the app is opened, *if* the last sync is stale
 * (>15 min) — the server deduplicates across tabs / devices / process restarts.
 *
 * This is what keeps the data fresh on a host with no always-on sync loop
 * (e.g. a free tier that sleeps): open the app → it catches up in the
 * background. The manual "Sync now" button (Positions) and the auto-sync
 * toggle are unchanged.
 *
 * When a cycle actually runs, a `tl:synced` window event is dispatched so the
 * page's data hooks refetch instead of showing pre-sync numbers.
 */
const STALE_MINUTES = 15

interface SyncOnOpenState {
  /** a catch-up sync is running right now */
  syncing: boolean
}

const Ctx = createContext<SyncOnOpenState>({ syncing: false })

export function useSyncOnOpen(): SyncOnOpenState {
  return useContext(Ctx)
}

// Module-level: run at most once per full page load, not per route change.
let started = false

export function SyncOnOpenProvider({ children }: { children: ReactNode }) {
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    if (started) return
    started = true

    // Fire-and-forget: this provider wraps the whole app and never unmounts,
    // so there is nothing to abort — let the catch-up finish either way.
    setSyncing(true)
    runSyncIfStale(STALE_MINUTES)
      .then((res) => {
        // `ran` is one cycle result, or an array (a user with several broker
        // connections). Fire `tl:synced` if any cycle brought in data.
        const runs = Array.isArray(res.ran) ? res.ran : res.ran ? [res.ran] : []
        if (runs.some((r) => r?.ok)) {
          window.dispatchEvent(new CustomEvent('tl:synced', { detail: runs }))
        }
      })
      .catch(() => {
        /* opening the app must never fail because a catch-up sync did */
      })
      .finally(() => setSyncing(false))
  }, [])

  return <Ctx.Provider value={{ syncing }}>{children}</Ctx.Provider>
}
