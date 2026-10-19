/**
 * The ONE place the app decides "what day is it" / "what day did this happen".
 *
 * Always the viewer's own clock — never UTC. `new Date().toISOString().slice(0, 10)` is the UTC date,
 * which in Manila (UTC+8) still says yesterday until 8am; that once made the calendar highlight Sunday
 * on a Monday morning. A guard test (tests/test_frontend_local_dates.py) fails the build if that
 * pattern, or a module-level "today" constant, comes back anywhere else in the app.
 *
 * "Today" also has to move on by itself: the desktop app stays open in the tray for days, so a value
 * worked out once when a page loaded goes stale at midnight. `useTodayIso()` re-renders at local
 * midnight, and whenever the window wakes up or regains focus (a sleeping PC misses timers).
 */
import { useEffect, useState } from 'react'

/** YYYY-MM-DD of the local calendar day a moment falls on. */
export function localDayIso(when: number | Date = Date.now()): string {
  const d = typeof when === 'number' ? new Date(when) : when
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Today's local date as YYYY-MM-DD. Call it when you need it — never store it in a module constant. */
export function todayIso(): string {
  return localDayIso(Date.now())
}

/** Milliseconds until the next local midnight (plus a small margin so we land safely past it). */
function msToNextMidnight(now: Date = new Date()): number {
  const next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 1)
  return Math.max(1_000, next.getTime() - now.getTime())
}

/** Today's local date, kept current: changes at local midnight and on wake / focus. */
export function useTodayIso(): string {
  const [today, setToday] = useState(todayIso)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    const refresh = () => {
      setToday(todayIso())
      clearTimeout(timer)
      timer = setTimeout(refresh, msToNextMidnight())
    }
    timer = setTimeout(refresh, msToNextMidnight())
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  return today
}

/** The viewer's IANA timezone (e.g. "Asia/Manila"), sent to the API so its days match ours. */
export function viewerTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null
  } catch {
    return null
  }
}
