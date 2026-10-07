import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { useAnalytics } from '../lib/useAnalytics'
import { useAuth } from '../lib/auth'
import { describeAccount, sortAccounts } from '../lib/accountLabel'
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

/** Home always shows ONE account — never every account mixed together. */
function loadAccount(): string | null {
  try {
    const v = localStorage.getItem(ACCOUNT_KEY)
    return v && v !== 'ALL' ? v : null
  } catch {
    return null
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
  const [account, setAccount] = useState<string | null>(loadAccount)
  const [hovered, setHovered] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const start = useMemo(() => isoDay(windowStartMs(WEEKS_WIDE)), [])
  const { state, data, error, refetch } = useAnalytics({ account: account ?? 'ALL', start })
  const accounts = useMemo(() => sortAccounts(data?.available.accounts ?? []), [data])

  // First visit (or the remembered account is gone): pick the first account in
  // the app's usual order — Capital.com, then MT5 — instead of mixing them.
  useEffect(() => {
    if (accounts.length && (!account || !accounts.includes(account))) setAccount(accounts[0])
  }, [accounts, account])

  // Only ever render figures that belong to the selected account. While a
  // switch is loading this is null and the skeleton shows, so one account's
  // numbers never sit under another account's name.
  const view = data && (accounts.length === 0 || (account && data.filters_applied.account === account)) ? data : null

  function pickAccount(a: string) {
    setAccount(a)
    setSelected(null)
    try {
      localStorage.setItem(ACCOUNT_KEY, a)
    } catch {
      /* per-device convenience only */
    }
  }

  const daily = view?.daily_pnl ?? []
  const grid = useMemo(() => buildGrid(daily, narrow ? WEEKS_NARROW : WEEKS_WIDE), [daily, narrow])
  const month = useMemo(() => monthSummary(daily), [daily])
  const streak = useMemo(() => currentStreak(daily), [daily])
  const { best, worst } = useMemo(() => bestAndWorst(daily), [daily])
  const topSymbol = useMemo(
    () => [...(view?.symbol_breakdown ?? [])].sort((a, b) => b.net_profit - a.net_profit)[0] ?? null,
    [view],
  )
  const monthPnl = useCountUp(month.pnl, 1300, 250)
  const winRate = useCountUp(view?.metrics.win_rate ?? 0, 1100, 450)
  const now = new Date()
  const name = firstName(user?.display_name, user?.email)
  const pf = view?.metrics.profit_factor ?? 0
  const shortcuts = ['workspace.journal', 'workspace.killzone-scanner', 'workspace.chart-analyzer', 'workspace.analytics']
    .map((id) => ALL_NAV_ITEMS.find((n) => n.id === id))
    .filter((n): n is NonNullable<typeof n> => Boolean(n))

  return (
    <div className="mx-auto w-full max-w-[1240px] px-4 py-6 sm:px-6 sm:py-8">
      {/* Which account this whole page is about — one at a time, never mixed */}
      {accounts.length ? (
        <div className="mb-5 flex flex-wrap items-center gap-2" role="radiogroup" aria-label="Account">
          <span className="mr-1 text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Account</span>
          {accounts.map((a) => {
            const info = describeAccount(a)
            const on = account === a
            return (
              <button
                key={a}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => pickAccount(a)}
                className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors ${
                  on ? 'border-accent bg-accent/10 font-semibold text-accent' : 'border-border text-secondary hover:bg-surface-hover hover:text-primary'
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${on ? 'bg-accent' : 'bg-border'}`} aria-hidden="true" />
                {info.label}
              </button>
            )
          })}
        </div>
      ) : null}

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
            {!view
              ? 'Pulling up your trades…'
              : month.tradingDays
                ? `${month.tradingDays} trading day${month.tradingDays === 1 ? '' : 's'} this month, ${month.greenDays} of them green.`
                : 'No closed trades yet this month — the calendar below picks up the moment one closes.'}
          </p>
        </div>

        <div className="tl-home-month">
          <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">
            This month{account ? ` · ${describeAccount(account).label}` : ''}
          </div>
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
          <dd>{view ? `${winRate.toFixed(1)}%` : '—'}</dd>
        </div>
        <div>
          <dt>Profit factor</dt>
          <dd>{view ? (Number.isFinite(pf) ? pf.toFixed(2) : '∞') : '—'}</dd>
        </div>
        <div>
          <dt>Day streak</dt>
          <dd className={streak ? (streak.green ? 'text-positive' : 'text-negative') : ''}>
            {streak ? `${streak.length} ${streak.green ? 'green' : 'red'}` : '—'}
          </dd>
        </div>
        <div>
          <dt>Trades · 6 mo</dt>
          <dd>{view ? view.metrics.total_trades : '—'}</dd>
        </div>
      </dl>

      {/* The calendar */}
      <section className="tl-home-card mt-5" aria-label="Daily P&L calendar">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-primary">Your last {narrow ? 'three' : 'six'} months, day by day</h2>
            <p className="text-xs text-muted">Hover a square or the line to see that day. Click a square to see its trades.</p>
          </div>
        </div>

        {state === 'error' && !data ? (
          <SectionError message={error ?? 'Your trades could not be loaded.'} onRetry={refetch} />
        ) : !view ? (
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

        {selected && account ? <DayTradesPanel iso={selected} account={account} onClose={() => setSelected(null)} /> : null}
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
