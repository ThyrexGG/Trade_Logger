import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { useAnalytics } from '../lib/useAnalytics'
import { useAuth } from '../lib/auth'
import { describeAccount } from '../lib/accountLabel'
import { formatSignedAmount } from '../lib/format'
import { ALL_NAV_ITEMS } from '../lib/navigation'
import type { IconComponent } from '../lib/icons'
import { SectionError } from '../components/operations/primitives'
import { PnlHeatmap } from '../components/home/PnlHeatmap'
import { DayTradesPanel } from '../components/home/DayTradesPanel'
import { useCountUp } from '../components/home/useCountUp'
import { bestAndWorst, buildGrid, currentStreak, monthSummary, prettyDate, windowStartMs, isoDay } from '../components/home/homeMath'

const WEEKS_WIDE = 26
const WEEKS_NARROW = 13
const ACCOUNT_KEY = 'tl.home.account'

function loadAccount(): string {
  try {
    return localStorage.getItem(ACCOUNT_KEY) || 'ALL'
  } catch {
    return 'ALL'
  }
}

function useNarrow(): boolean {
  const query = '(max-width: 639px)'
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const on = () => setNarrow(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return narrow
}

function greeting(now: Date): string {
  const h = now.getHours()
  if (h < 5) return 'Late one'
  if (h < 12) return 'Morning'
  if (h < 18) return 'Afternoon'
  return 'Evening'
}

/** Which FX sessions are open right now (UTC hours, ignoring DST shifts of an hour). */
function sessionLabel(now: Date): string {
  const day = now.getUTCDay()
  const h = now.getUTCHours()
  if (day === 6 || (day === 0 && h < 21) || (day === 5 && h >= 21)) return 'Markets closed for the weekend'
  const open = [
    (h >= 21 || h < 6) && 'Sydney',
    h < 9 && 'Tokyo',
    h >= 7 && h < 16 && 'London',
    h >= 12 && h < 21 && 'New York',
  ].filter(Boolean) as string[]
  if (open.length === 0) return 'Between sessions'
  return open.length > 1 ? `${open.join(' + ')} overlap` : `${open[0]} session open`
}

function firstName(display: string | null | undefined, email: string | undefined): string {
  const raw = (display || email?.split('@')[0] || '').trim()
  const word = raw.split(/[\s._-]+/)[0] ?? ''
  return word ? word[0].toUpperCase() + word.slice(1) : ''
}

/**
 * Home (`/workspace/home`) — the first screen after sign-in. Built around one
 * picture: six months of daily P&L as a heatmap that fills itself in, with the
 * running total drawn underneath along the same weeks. Everything comes from
 * the same analytics endpoint the Analytics page uses; nothing is invented.
 */
export function HomePage() {
  const { user } = useAuth()
  const narrow = useNarrow()
  const [account, setAccount] = useState(loadAccount)
  const [hovered, setHovered] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const start = useMemo(() => isoDay(windowStartMs(WEEKS_WIDE)), [])
  const { state, data, error, refetch } = useAnalytics({ account, start })

  function pickAccount(a: string) {
    setAccount(a)
    setSelected(null)
    try {
      localStorage.setItem(ACCOUNT_KEY, a)
    } catch {
      /* per-device convenience only */
    }
  }

  const daily = data?.daily_pnl ?? []
  const grid = useMemo(() => buildGrid(daily, narrow ? WEEKS_NARROW : WEEKS_WIDE), [daily, narrow])
  const month = useMemo(() => monthSummary(daily), [daily])
  const streak = useMemo(() => currentStreak(daily), [daily])
  const { best, worst } = useMemo(() => bestAndWorst(daily), [daily])
  const topSymbol = useMemo(
    () => [...(data?.symbol_breakdown ?? [])].sort((a, b) => b.net_profit - a.net_profit)[0] ?? null,
    [data],
  )
  const monthPnl = useCountUp(month.pnl, 1300, 250)
  const winRate = useCountUp(data?.metrics.win_rate ?? 0, 1100, 450)
  const now = new Date()
  const name = firstName(user?.display_name, user?.email)
  const accounts = data?.available.accounts ?? []
  const pf = data?.metrics.profit_factor ?? 0
  const shortcuts = ['workspace.journal', 'workspace.killzone-scanner', 'workspace.chart-analyzer', 'workspace.analytics']
    .map((id) => ALL_NAV_ITEMS.find((n) => n.id === id))
    .filter((n): n is NonNullable<typeof n> => Boolean(n))

  return (
    <div className="mx-auto w-full max-w-[1240px] px-4 py-6 sm:px-6 sm:py-8">
      {/* Greeting + this month */}
      <header className="tl-home-hero">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">
            {now.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })} · {sessionLabel(now)}
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-primary [text-wrap:balance] sm:text-4xl">
            {greeting(now)}
            {name ? `, ${name}` : ''}.
          </h1>
          <p className="mt-2 max-w-xl text-sm text-secondary">
            {state === 'loading' && !data
              ? 'Pulling up your trades…'
              : month.tradingDays
                ? `${month.tradingDays} trading day${month.tradingDays === 1 ? '' : 's'} this month, ${month.greenDays} of them green.`
                : 'No closed trades yet this month — the calendar below picks up the moment one closes.'}
          </p>
        </div>

        <div className="tl-home-month">
          <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">This month</div>
          <div className={`font-mono text-4xl font-semibold tabular-nums sm:text-5xl ${month.pnl > 0 ? 'text-positive' : month.pnl < 0 ? 'text-negative' : 'text-primary'}`}>
            {formatSignedAmount(monthPnl)}
          </div>
          <div className="mt-1 text-xs text-muted">{month.trades} closed trade{month.trades === 1 ? '' : 's'}</div>
        </div>
      </header>

      {/* Stat strip */}
      <dl className="tl-home-stats">
        <div>
          <dt>Win rate</dt>
          <dd>{data ? `${winRate.toFixed(1)}%` : '—'}</dd>
        </div>
        <div>
          <dt>Profit factor</dt>
          <dd>{data ? (Number.isFinite(pf) ? pf.toFixed(2) : '∞') : '—'}</dd>
        </div>
        <div>
          <dt>Day streak</dt>
          <dd className={streak ? (streak.green ? 'text-positive' : 'text-negative') : ''}>
            {streak ? `${streak.length} ${streak.green ? 'green' : 'red'}` : '—'}
          </dd>
        </div>
        <div>
          <dt>Trades · 6 mo</dt>
          <dd>{data ? data.metrics.total_trades : '—'}</dd>
        </div>
      </dl>

      {/* The calendar */}
      <section className="tl-home-card mt-5" aria-label="Daily P&L calendar">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-primary">Your last {narrow ? 'three' : 'six'} months, day by day</h2>
            <p className="text-xs text-muted">Hover a square or the line to see that day. Click a square to see its trades.</p>
          </div>
          {accounts.length > 1 ? (
            <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Account">
              {['ALL', ...accounts].map((a) => (
                <button
                  key={a}
                  type="button"
                  role="radio"
                  aria-checked={account === a}
                  onClick={() => pickAccount(a)}
                  className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
                    account === a ? 'border-accent bg-accent/10 text-accent' : 'border-border text-secondary hover:bg-surface-hover'
                  }`}
                >
                  {a === 'ALL' ? 'All accounts' : describeAccount(a).label}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {state === 'error' && !data ? (
          <SectionError message={error ?? 'Your trades could not be loaded.'} onRetry={refetch} />
        ) : !data ? (
          <div className="tl-heat-skeleton" aria-busy="true" aria-label="Loading">
            {Array.from({ length: 7 }, (_, i) => (
              <div key={i} />
            ))}
          </div>
        ) : (
          <PnlHeatmap
            key={`${account}-${grid.weeks}`}
            grid={grid}
            hovered={hovered}
            selected={selected}
            onHover={setHovered}
            onSelect={(iso) => setSelected((cur) => (cur === iso ? null : iso))}
          />
        )}

        <div className="mt-3 flex items-center justify-end gap-1.5 text-[10px] text-muted" aria-hidden="true">
          <span>Loss</span>
          {[1, 0.6, 0.3].map((t) => (
            <i key={`n${t}`} className="tl-legend-sq" style={{ background: `color-mix(in oklab, var(--tl-negative) ${28 + t * 72}%, var(--tl-surface-elevated))` }} />
          ))}
          <i className="tl-legend-sq" style={{ background: 'var(--tl-surface-elevated)' }} />
          {[0.3, 0.6, 1].map((t) => (
            <i key={`p${t}`} className="tl-legend-sq" style={{ background: `color-mix(in oklab, var(--tl-positive) ${28 + t * 72}%, var(--tl-surface-elevated))` }} />
          ))}
          <span>Profit</span>
        </div>

        {selected ? <DayTradesPanel iso={selected} account={account} onClose={() => setSelected(null)} /> : null}
      </section>

      {/* Highlights */}
      <section className="mt-5 grid gap-3 sm:grid-cols-3" aria-label="Highlights">
        <Highlight
          label="Best day"
          value={best ? formatSignedAmount(best.net_profit) : '—'}
          tone="positive"
          sub={best ? prettyDate(best.date) : 'No green day yet'}
          onClick={best ? () => setSelected(best.date) : undefined}
        />
        <Highlight
          label="Toughest day"
          value={worst ? formatSignedAmount(worst.net_profit) : '—'}
          tone="negative"
          sub={worst ? prettyDate(worst.date) : 'No red day — nice'}
          onClick={worst ? () => setSelected(worst.date) : undefined}
        />
        <Highlight
          label="Top symbol"
          value={topSymbol ? topSymbol.symbol : '—'}
          tone="accent"
          sub={topSymbol ? `${formatSignedAmount(topSymbol.net_profit)} · ${topSymbol.trades} trades · ${topSymbol.win_rate.toFixed(0)}% won` : 'Trade a little first'}
        />
      </section>

      {/* Shortcuts */}
      {shortcuts.length ? (
        <section className="mt-5" aria-label="Jump back in">
          <h2 className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Jump back in</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {shortcuts.map((n, i) => (
              <SpotlightLink key={n.id} to={n.path} index={i} title={n.label} body={n.description} Icon={n.icon} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}

function Highlight({
  label,
  value,
  sub,
  tone,
  onClick,
}: {
  label: string
  value: string
  sub: string
  tone: 'positive' | 'negative' | 'accent'
  onClick?: () => void
}) {
  const color = tone === 'positive' ? 'text-positive' : tone === 'negative' ? 'text-negative' : 'text-accent'
  const body = (
    <>
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className={`mt-1 font-mono text-2xl font-semibold ${color}`}>{value}</div>
      <div className="mt-0.5 text-xs text-secondary">{sub}</div>
    </>
  )
  return onClick ? (
    <button type="button" onClick={onClick} className="tl-home-card tl-reveal text-left transition-colors hover:border-accent">
      {body}
    </button>
  ) : (
    <div className="tl-home-card tl-reveal">{body}</div>
  )
}

function SpotlightLink({
  to,
  title,
  body,
  index,
  Icon,
}: {
  to: string
  title: string
  body: string
  index: number
  Icon: IconComponent
}) {
  return (
    <Link
      to={to}
      className="tl-spotlight tl-reveal"
      style={{ '--i': index } as CSSProperties}
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect()
        e.currentTarget.style.setProperty('--sx', `${e.clientX - r.left}px`)
        e.currentTarget.style.setProperty('--sy', `${e.clientY - r.top}px`)
      }}
    >
      <Icon className="h-5 w-5 text-accent" />
      <div className="mt-3 text-sm font-semibold text-primary">{title}</div>
      <div className="mt-1 text-xs leading-relaxed text-secondary">{body}</div>
    </Link>
  )
}
