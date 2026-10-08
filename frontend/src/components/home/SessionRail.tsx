import { useEffect, useMemo, useState } from 'react'
import { formatSignedAmount } from '../../lib/format'
import { KILLZONES, SESSIONS, formatDuration, localDayStart, placeWindows, type PlacedWindow } from './sessions'

export interface RailTrade {
  id: string
  /** ISO time the trade closed */
  at: string
  pnl: number
  symbol: string
}

export interface RailOpen {
  id: string
  /** ISO time the position opened */
  at: string
  symbol: string
}

const TICKS = [0, 3, 6, 9, 12, 15, 18, 21]

function pct(f: number): string {
  return `${(f * 100).toFixed(3)}%`
}

function timeLabel(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * Session Rail — today on one line, on your own clock. The four FX sessions as
 * lanes, the ICT killzones as faint bands across them, a live "now" marker,
 * and your own trades placed where they happened: closes as ticks (green or
 * red), still-open positions as rings at the time you opened them. It answers
 * "where am I in the trading day, and what have I done in it?" at a glance.
 */
export function SessionRail({ trades, open }: { trades: RailTrade[]; open: RailOpen[] }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(id)
  }, [])

  const dayStart = localDayStart(now)
  const dayKey = dayStart
  const lanes = useMemo(
    () => SESSIONS.map((s) => ({ ...s, spans: placeWindows([s], dayKey) })),
    [dayKey],
  )
  const zones = useMemo(() => placeWindows(KILLZONES, dayKey).filter((z) => !z.label.startsWith('Asian')), [dayKey])
  const nowF = (now - dayStart) / 86_400_000

  const status = useMemo(() => describeNow(now, lanes.flatMap((l) => l.spans.map((s) => ({ ...s, lane: l.label }))), zones), [now, lanes, zones])

  const place = (iso: string) => {
    const ms = Date.parse(iso)
    if (!Number.isFinite(ms) || ms < dayStart || ms >= dayStart + 86_400_000) return null
    return (ms - dayStart) / 86_400_000
  }

  return (
    <section className="tl-card px-4 pb-3 pt-3.5 sm:px-5" aria-label="Trading sessions today">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="tl-label">Sessions · your time</p>
        <p className="text-[13px] text-secondary">
          <span className="text-primary">{status.open}</span>
          {status.next ? <span className="text-muted"> · {status.next}</span> : null}
        </p>
      </div>

      <div className="grid grid-cols-[4.75rem_minmax(0,1fr)] gap-x-3">
        <div className="flex flex-col gap-[7px] pt-px">
          {lanes.map((l) => (
            <span key={l.id} className="h-[9px] font-mono text-[10.5px] leading-[9px] text-muted">
              {l.label}
            </span>
          ))}
          <span className="mt-1 h-[14px] font-mono text-[10.5px] leading-[14px] text-muted">You</span>
        </div>

        <div className="relative">
          {/* hour grid */}
          {TICKS.map((h) => (
            <span key={h} className="absolute bottom-0 top-0 w-px bg-[var(--tl-grid-line)]" style={{ left: pct(h / 24) }} aria-hidden="true" />
          ))}
          {/* killzones */}
          {zones.map((z) => (
            <span
              key={z.id}
              className="absolute bottom-0 top-0 rounded-[3px] bg-accent-soft"
              style={{ left: pct(z.from), width: pct(z.to - z.from) }}
              title={`${z.label}: ${timeLabel(z.startMs)}–${timeLabel(z.endMs)}`}
              aria-hidden="true"
            />
          ))}

          <div className="relative flex flex-col gap-[7px]">
            {lanes.map((l) => (
              <div key={l.id} className="relative h-[9px] rounded-full bg-[var(--tl-grid-line)]">
                {l.spans.map((s) => {
                  const live = nowF >= s.from && nowF < s.to
                  return (
                    <span
                      key={s.id}
                      className={`absolute bottom-0 top-0 rounded-full ${live ? 'bg-[var(--tl-text-secondary)]' : 'bg-[var(--tl-border)]'}`}
                      style={{ left: pct(s.from), width: pct(s.to - s.from) }}
                      title={`${l.label} session: ${timeLabel(s.startMs)}–${timeLabel(s.endMs)}`}
                    />
                  )
                })}
              </div>
            ))}

            {/* your trades */}
            <div className="relative mt-1 h-[14px]">
              <span className="absolute inset-x-0 top-1/2 h-px bg-[var(--tl-grid-line)]" aria-hidden="true" />
              {trades.map((t) => {
                const f = place(t.at)
                if (f == null) return null
                return (
                  <span
                    key={t.id}
                    className={`absolute top-0 h-[14px] w-[3px] -translate-x-1/2 rounded-full ${t.pnl >= 0 ? 'bg-positive' : 'bg-negative'}`}
                    style={{ left: pct(f) }}
                    title={`${t.symbol} closed ${timeLabel(Date.parse(t.at))} · ${formatSignedAmount(t.pnl)}`}
                  />
                )
              })}
              {open.map((p) => {
                const f = place(p.at)
                if (f == null) return null
                return (
                  <span
                    key={p.id}
                    className="absolute top-1/2 h-[9px] w-[9px] -translate-x-1/2 -translate-y-1/2 rounded-full border-[1.5px] border-accent-fill bg-surface"
                    style={{ left: pct(f) }}
                    title={`${p.symbol} opened ${timeLabel(Date.parse(p.at))} — still open`}
                  />
                )
              })}
            </div>
          </div>

          {/* now */}
          <span className="pointer-events-none absolute -bottom-1 -top-1 w-px bg-accent-fill" style={{ left: pct(nowF) }} aria-hidden="true">
            <span className="absolute -left-[3px] -top-1 h-[7px] w-[7px] rounded-full bg-accent-fill" />
          </span>
        </div>

        <span />
        <div className="relative mt-1.5 h-4">
          {TICKS.map((h) => (
            <span key={h} className="absolute -translate-x-1/2 font-mono text-[10px] text-muted first:translate-x-0" style={{ left: pct(h / 24) }}>
              {String(h).padStart(2, '0')}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

function describeNow(now: number, spans: (PlacedWindow & { lane: string })[], zones: PlacedWindow[]) {
  // Spot FX closes from Friday 21:00 to Sunday 21:00 UTC.
  const d = new Date(now)
  const day = d.getUTCDay()
  const h = d.getUTCHours()
  if (day === 6 || (day === 0 && h < 21) || (day === 5 && h >= 21)) {
    const reopen = new Date(now)
    reopen.setUTCDate(reopen.getUTCDate() + ((7 - day) % 7))
    reopen.setUTCHours(21, 0, 0, 0)
    return { open: 'Markets closed for the weekend', next: `reopen in ${formatDuration(reopen.getTime() - now)}` }
  }
  const open = [...new Set(spans.filter((s) => now >= s.startMs && now < s.endMs).map((s) => s.lane))]
  const openText = open.length === 0 ? 'Between sessions' : open.length === 1 ? `${open[0]} open` : `${open.join(' + ')} open`
  const inZone = zones.find((z) => now >= z.startMs && now < z.endMs)
  if (inZone) return { open: openText, next: `${inZone.label} — ends in ${formatDuration(inZone.endMs - now)}` }
  const upcoming = zones.filter((z) => z.startMs > now).sort((a, b) => a.startMs - b.startMs)[0]
  return { open: openText, next: upcoming ? `${upcoming.label} in ${formatDuration(upcoming.startMs - now)}` : null }
}
