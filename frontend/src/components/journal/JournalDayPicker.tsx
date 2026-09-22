import { useEffect, useMemo, useRef, useState } from 'react'
import { formatUsd } from '../../lib/format'
import type { JournalTradeItem } from '../../types/operations'

const WEEKDAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function signedUsd(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v)}`
}

/** Treats a timestamp with no explicit timezone as UTC — matching how the backend stores `exit_time`. */
function parseTime(iso: string): number {
  const hasZone = /[zZ]|[+-]\d\d:\d\d$/.test(iso)
  const t = new Date(hasZone ? iso : `${iso}Z`).getTime()
  return Number.isNaN(t) ? 0 : t
}

/** The local calendar day (YYYY-MM-DD) a timestamp falls on — the same "what day did I actually see this"
 * bucketing the rest of the journal's date filters use, not the trade's UTC day. */
export function localDayIso(ms: number): string {
  const d = new Date(ms)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Monday-indexed weekday (0 = Mon … 6 = Sun). */
function mondayIndex(d: Date): number {
  return (d.getDay() + 6) % 7
}

const TODAY_ISO = localDayIso(Date.now())

interface DayCell {
  day: number
  iso: string
  inMonth: boolean
  net: number
  trades: number
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 10h18" strokeLinecap="round" />
    </svg>
  )
}

/**
 * "Pick a day" for the Journal: a compact button that opens a month calendar in the style of the Analytics
 * calendar, colored by that day's net P&L. Unlike Analytics it needs no request — the journal already has
 * every entry client-side, so this just groups what's already loaded and filters in place.
 */
export function JournalDayPicker({
  entries,
  selected,
  onSelect,
}: {
  /** Already scoped to the current account filter; NOT date-filtered (the calendar needs the full range). */
  entries: JournalTradeItem[]
  selected: string | null
  onSelect: (iso: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  const byDay = useMemo(() => {
    const map = new Map<string, { net: number; trades: number }>()
    for (const e of entries) {
      const iso = localDayIso(parseTime(e.exit_time))
      const cur = map.get(iso) ?? { net: 0, trades: 0 }
      cur.net += e.net_profit
      cur.trades += 1
      map.set(iso, cur)
    }
    return map
  }, [entries])

  const latestIso = useMemo(
    () => entries.reduce<string | null>((max, e) => {
      const iso = localDayIso(parseTime(e.exit_time))
      return !max || iso > max ? iso : max
    }, null),
    [entries],
  )

  const [cursor, setCursor] = useState(() => {
    const base = new Date(`${selected ?? latestIso ?? TODAY_ISO}T00:00:00`)
    return { y: base.getFullYear(), m: base.getMonth() }
  })

  // Jump to the selected/latest month whenever the popover opens, so re-opening it doesn't strand you on
  // whatever month you last scrolled to.
  useEffect(() => {
    if (!open) return
    const base = new Date(`${selected ?? latestIso ?? TODAY_ISO}T00:00:00`)
    setCursor({ y: base.getFullYear(), m: base.getMonth() })
  }, [open, selected, latestIso])

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const firstDay = new Date(cursor.y, cursor.m, 1)
  const daysInMonth = new Date(cursor.y, cursor.m + 1, 0).getDate()
  const lead = mondayIndex(firstDay)

  const cells: DayCell[] = []
  for (let i = 0; i < lead; i += 1) cells.push({ day: 0, iso: `lead-${i}`, inMonth: false, net: 0, trades: 0 })
  for (let day = 1; day <= daysInMonth; day += 1) {
    const iso = `${cursor.y}-${String(cursor.m + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    const d = byDay.get(iso)
    cells.push({ day, iso, inMonth: true, net: d?.net ?? 0, trades: d?.trades ?? 0 })
  }
  while (cells.length % 7 !== 0) cells.push({ day: 0, iso: `trail-${cells.length}`, inMonth: false, net: 0, trades: 0 })

  const dayMax = Math.max(1, ...cells.filter((c) => c.trades > 0).map((c) => Math.abs(c.net)))
  const selectedLabel = selected
    ? new Date(`${selected}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : null

  return (
    <div className="relative" ref={boxRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs ${
          selected ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-secondary hover:bg-surface-hover'
        }`}
        aria-expanded={open}
        title="Pick a day to show just that day's trades"
      >
        <CalendarIcon />
        {selectedLabel ?? 'Calendar'}
        {selected ? (
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => { e.stopPropagation(); onSelect(null) }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); onSelect(null) } }}
            aria-label="Clear the selected day"
            className="ml-0.5 rounded-full px-1 leading-none hover:bg-accent/20"
          >
            ×
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-20 mt-1 w-72 rounded-lg border border-border bg-surface p-3 shadow-lg">
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setCursor((c) => (c.m === 0 ? { y: c.y - 1, m: 11 } : { y: c.y, m: c.m - 1 }))}
              className="rounded p-1 text-muted hover:bg-surface-hover hover:text-primary"
              aria-label="Previous month"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <span className="text-xs font-semibold text-primary">{MONTHS[cursor.m]} {cursor.y}</span>
            <button
              type="button"
              onClick={() => setCursor((c) => (c.m === 11 ? { y: c.y + 1, m: 0 } : { y: c.y, m: c.m + 1 }))}
              className="rounded p-1 text-muted hover:bg-surface-hover hover:text-primary"
              aria-label="Next month"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>

          <div className="grid grid-cols-7 text-center text-[9px] uppercase tracking-wide text-muted">
            {WEEKDAYS.map((w, i) => <div key={`${w}-${i}`} className="pb-1">{w}</div>)}
          </div>
          <div className="grid grid-cols-7 gap-0.5">
            {cells.map((c) => {
              if (!c.inMonth) return <div key={c.iso} className="aspect-square" />
              const isToday = c.iso === TODAY_ISO
              const isSelected = c.iso === selected
              const hasTrades = c.trades > 0
              const intensity = hasTrades ? Math.min(0.32, 0.08 + (Math.abs(c.net) / dayMax) * 0.24) : 0
              const bg = hasTrades ? (c.net >= 0 ? `rgba(34,197,94,${intensity})` : `rgba(239,68,68,${intensity})`) : undefined
              return (
                <button
                  key={c.iso}
                  type="button"
                  disabled={!hasTrades}
                  onClick={() => { onSelect(isSelected ? null : c.iso); setOpen(false) }}
                  title={hasTrades ? `${c.iso} · ${signedUsd(c.net)} · ${c.trades} trade${c.trades === 1 ? '' : 's'}` : c.iso}
                  style={bg ? { backgroundColor: bg } : undefined}
                  className={`flex aspect-square flex-col items-center justify-center rounded text-[10px] tabular-nums ${
                    hasTrades ? 'cursor-pointer' : 'cursor-default text-muted/40'
                  } ${isSelected ? 'ring-2 ring-inset ring-accent' : isToday ? 'ring-1 ring-inset ring-accent/50' : ''}`}
                >
                  <span className={isToday ? 'font-semibold text-accent' : hasTrades ? 'text-secondary' : ''}>{c.day}</span>
                </button>
              )
            })}
          </div>
          <p className="mt-2 text-[10px] text-muted">Shaded days closed a trade — green net winners, red net losers.</p>
        </div>
      ) : null}
    </div>
  )
}
