import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAnalytics } from '../lib/useAnalytics'
import { useOpenPositions } from '../lib/useOpenPositions'
import { useAlerts } from '../lib/useAlerts'
import { useCachedResource } from '../lib/dataCache'
import { getDayTrades } from '../api/analytics'
import { describeAccount, sortAccounts } from '../lib/accountLabel'
import { formatPrice, formatSignedAmount } from '../lib/format'
import { SectionError } from '../components/operations/primitives'
import { PnlHeatmap } from '../components/home/PnlHeatmap'
import { DayTradesPanel } from '../components/home/DayTradesPanel'
import { MarketStrip } from '../components/home/MarketStrip'
import { SessionRail } from '../components/home/SessionRail'
import { PositionTracks } from '../components/home/PositionTracks'
import { useCountUp } from '../components/home/useCountUp'
import { bestAndWorst, buildGrid, currentStreak, monthSummary, prettyDate, windowStartMs, isoDay } from '../components/home/homeMath'

const WEEKS_MAX = 26
const WEEKS_MIN = 13
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

function isLong(direction: string): boolean {
  const d = direction.toUpperCase()
  return d.startsWith('B') || d === 'LONG'
}

function tone(v: number): string {
  return v > 0 ? 'text-positive' : v < 0 ? 'text-negative' : 'text-primary'
}

/**
 * Today (`/workspace/home`) — the command centre. Laid out by urgency, top to
 * bottom: what the market is doing and where we are in the trading day; what
 * is open and at risk right now; how today is going; then the longer view.
 * One account at a time; every figure comes from the same APIs the rest of
 * the app uses.
 */
export function HomePage() {
  const narrow = useNarrow()
  const [account, setAccount] = useState<string | null>(loadAccount)
  const [hovered, setHovered] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const start = useMemo(() => isoDay(windowStartMs(WEEKS_MAX)), [])
  const { state, data, error, refetch } = useAnalytics({ account: account ?? 'ALL', start })
  const accounts = useMemo(() => sortAccounts(data?.available.accounts ?? []), [data])
  const positions = useOpenPositions()
  const alerts = useAlerts()

  // First visit (or the remembered account is gone): pick the first account in
  // the app's usual order — Capital.com, then MT5 — instead of mixing them.
  useEffect(() => {
    if (accounts.length && (!account || !accounts.includes(account))) setAccount(accounts[0])
  }, [accounts, account])

  // Only ever render figures that belong to the selected account.
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

  const todayIso = isoDay(Date.now())
  const todayTrades = useCachedResource(
    `home:day:${account ?? 'ALL'}:${todayIso}`,
    (signal) => getDayTrades(todayIso, { account: account ?? 'ALL' }, signal),
    { refreshMs: 120_000, revalidateOn: ['tl:synced'] },
  )

  const daily = view?.daily_pnl ?? []
  const weeks = useMemo(() => {
    if (narrow) return WEEKS_MIN
    const first = daily.reduce<string | null>((m, d) => (!m || d.date < m ? d.date : m), null)
    if (!first) return WEEKS_MIN
    const since = Math.ceil((Date.now() - Date.parse(`${first.slice(0, 10)}T00:00:00Z`)) / (7 * 86_400_000)) + 1
    return Math.max(WEEKS_MIN, Math.min(WEEKS_MAX, since))
  }, [daily, narrow])
  const grid = useMemo(() => buildGrid(daily, weeks), [daily, weeks])
  const month = useMemo(() => monthSummary(daily), [daily])
  const today = useMemo(() => daily.find((d) => d.date.slice(0, 10) === todayIso) ?? null, [daily, todayIso])
  const streak = useMemo(() => currentStreak(daily), [daily])
  const { best, worst } = useMemo(() => bestAndWorst(daily), [daily])
  const topSymbol = useMemo(() => [...(view?.symbol_breakdown ?? [])].sort((a, b) => b.net_profit - a.net_profit)[0] ?? null, [view])

  const open = useMemo(
    () => (positions.data?.positions ?? []).filter((p) => !account || p.account_id === account),
    [positions.data, account],
  )
  const floating = open.reduce((s, p) => s + p.floating_pnl, 0)
  const unprotected = open.filter((p) => !(p.sl > 0)).length
  const waiting = (alerts.data?.alerts ?? []).filter((a) => a.status.toUpperCase() === 'ACTIVE')
  const closedToday = todayTrades.data?.trades ?? []

  const monthPnl = useCountUp(month.pnl, 900, 100)
  const todayPnl = useCountUp(today?.net_profit ?? 0, 900, 100)
  const now = new Date()
  const yourSymbols = useMemo(() => (view?.symbol_breakdown ?? []).map((r) => r.symbol), [view])

  return (
    <div className="mx-auto w-full max-w-[1320px] space-y-4 px-4 py-6 sm:px-6 sm:py-7">
      {/* Header */}
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div>
          <p className="tl-eyebrow">
            {now.toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short' })} ·{' '}
            {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </p>
          <h1 className="tl-page-title mt-1">Overview</h1>
        </div>
        {accounts.length ? (
          <div className="tl-seg" role="radiogroup" aria-label="Account">
            {accounts.map((a) => (
              <button key={a} type="button" role="radio" aria-checked={account === a} onClick={() => pickAccount(a)}>
                <span className={`h-1.5 w-1.5 rounded-full ${account === a ? 'bg-accent-fill' : 'bg-[var(--tl-border)]'}`} aria-hidden="true" />
                {describeAccount(a).label}
              </button>
            ))}
          </div>
        ) : null}
      </header>

      {/* Level 1 — the market and the trading day */}
      <MarketStrip yourSymbols={yourSymbols} />
      <SessionRail
        trades={closedToday.map((t) => ({ id: t.trade_id, at: t.exit_time, pnl: t.net_profit, symbol: t.symbol }))}
        open={open.filter((p) => p.open_time).map((p) => ({ id: p.position_id, at: p.open_time as string, symbol: p.symbol }))}
      />

      {/* Level 1/2 — your book right now, and today */}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <section className="tl-card" aria-label="Your account now">
          <dl className="grid grid-cols-2 border-b border-[var(--tl-border-subtle)] sm:grid-cols-4">
            {[
              { label: 'Today', value: view ? formatSignedAmount(todayPnl) : '—', cls: tone(today?.net_profit ?? 0), sub: today ? `${today.trades} closed` : 'no closed trades' },
              { label: 'Open now', value: positions.data ? formatSignedAmount(floating) : '—', cls: tone(floating), sub: `${open.length} trade${open.length === 1 ? '' : 's'} running` },
              { label: 'This month', value: view ? formatSignedAmount(monthPnl) : '—', cls: tone(month.pnl), sub: `${month.greenDays}/${month.tradingDays} days green` },
              { label: 'Win rate · 6 mo', value: view ? `${view.metrics.win_rate.toFixed(1)}%` : '—', cls: 'text-primary', sub: view ? `profit factor ${Number.isFinite(view.metrics.profit_factor) ? view.metrics.profit_factor.toFixed(2) : '∞'}` : '' },
            ].map((f, i) => (
              <div key={f.label} className={`px-4 py-3.5 sm:px-5 ${i % 2 ? 'border-l border-[var(--tl-border-subtle)]' : ''} ${i === 2 ? 'border-t border-[var(--tl-border-subtle)] sm:border-l sm:border-t-0' : ''} ${i === 3 ? 'border-t border-[var(--tl-border-subtle)] sm:border-t-0' : ''}`}>
                <dt className="tl-label">{f.label}</dt>
                <dd className={`tl-figure mt-1 text-[1.35rem] leading-none sm:text-[1.5rem] ${f.cls}`}>{f.value}</dd>
                <dd className="mt-1.5 text-xs text-muted">{f.sub}</dd>
              </div>
            ))}
          </dl>

          <div className="px-4 pb-3 pt-3.5 sm:px-5">
            <div className="mb-2 flex items-center gap-3">
              <h2 className="text-[13.5px] font-semibold text-primary">Open trades</h2>
              <span className="tl-rule" aria-hidden="true" />
              {unprotected ? (
                <span className="flex items-center gap-1.5 text-xs text-warning">
                  <span className="h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true" />
                  {unprotected} without a stop loss
                </span>
              ) : open.length ? (
                <span className="flex items-center gap-1.5 text-xs text-muted">
                  <span className="h-1.5 w-1.5 rounded-full bg-positive" aria-hidden="true" />
                  All protected by a stop loss
                </span>
              ) : null}
              <Link to="/workspace/positions" className="text-xs text-muted hover:text-accent">
                All positions →
              </Link>
            </div>
            {positions.state === 'loading' && !positions.data ? (
              <div className="space-y-2 py-1">
                <span className="tl-skeleton block h-8 rounded" />
                <span className="tl-skeleton block h-8 rounded" />
              </div>
            ) : positions.state === 'error' && !positions.data ? (
              <p className="py-2 text-sm text-muted">Couldn&rsquo;t load your open trades right now.</p>
            ) : (
              <PositionTracks positions={open} />
            )}
          </div>
        </section>

        <div className="space-y-4">
          <section className="tl-card" aria-label="Closed today">
            <div className="tl-card-head">
              <h2 className="tl-card-title">Closed today</h2>
              <span className="tl-rule" aria-hidden="true" />
              <Link to="/workspace/journal" className="text-xs text-muted hover:text-accent">
                Journal →
              </Link>
            </div>
            <div className="tl-card-body">
              {todayTrades.state === 'loading' && !todayTrades.data ? (
                <span className="tl-skeleton block h-6 rounded" />
              ) : closedToday.length === 0 ? (
                <p className="text-sm text-muted">Nothing closed yet today.</p>
              ) : (
                <ul className="space-y-1.5">
                  {closedToday.slice(0, 6).map((t) => (
                    <li key={t.trade_id}>
                      <Link to={`/workspace/journal?trade=${encodeURIComponent(t.trade_id)}`} className="-mx-2 grid grid-cols-[3rem_minmax(0,1fr)_auto] items-baseline gap-2 rounded-[var(--tl-radius-sm)] px-2 py-1 hover:bg-surface-elevated">
                        <span className="font-mono text-[11px] text-muted">{new Date(t.exit_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        <span className="truncate text-sm text-primary">
                          <span className={`mr-1.5 font-mono text-[10.5px] ${isLong(t.direction) ? 'text-positive' : 'text-negative'}`}>{isLong(t.direction) ? 'BUY' : 'SELL'}</span>
                          {t.symbol}
                        </span>
                        <span className={`tl-figure text-sm ${tone(t.net_profit)}`}>{formatSignedAmount(t.net_profit)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="tl-card" aria-label="Price alerts">
            <div className="tl-card-head">
              <h2 className="tl-card-title">Price alerts</h2>
              <span className="tl-rule" aria-hidden="true" />
              <Link to="/workspace/alerts" className="text-xs text-muted hover:text-accent">
                {waiting.length ? 'Manage →' : 'Set one →'}
              </Link>
            </div>
            <div className="tl-card-body">
              {alerts.state === 'loading' && !alerts.data ? (
                <span className="tl-skeleton block h-6 rounded" />
              ) : waiting.length === 0 ? (
                <p className="text-sm text-muted">No alerts waiting.</p>
              ) : (
                <ul className="space-y-1">
                  {waiting.slice(0, 5).map((a) => (
                    <li key={a.id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-baseline gap-3 py-0.5">
                      <span className="truncate font-mono text-[12.5px] text-primary">{a.symbol}</span>
                      <span className="font-mono text-[11px] text-muted">{a.condition === 'ABOVE' ? '≥' : '≤'}</span>
                      <span className="tl-figure text-sm text-secondary">{formatPrice(a.target_price)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* Level 3 — the longer view */}
      <section className="tl-card" aria-label="Performance">
        <div className="tl-card-head">
          <h2 className="tl-card-title">Performance</h2>
          <span className="tl-label hidden sm:inline">{weeks === WEEKS_MAX ? 'last 6 months' : `last ${weeks} weeks`}</span>
          <span className="tl-rule" aria-hidden="true" />
          <Link to="/workspace/analytics" className="text-xs text-muted hover:text-accent">
            Analytics →
          </Link>
        </div>
        <div className="tl-card-body">
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

          {view ? (
            <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-[var(--tl-border-subtle)] pt-3.5 sm:grid-cols-4">
              <Highlight label="Best day" value={best ? formatSignedAmount(best.net_profit) : '—'} sub={best ? prettyDate(best.date) : 'no green day yet'} cls="text-positive" onClick={best ? () => setSelected(best.date) : undefined} />
              <Highlight label="Toughest day" value={worst ? formatSignedAmount(worst.net_profit) : '—'} sub={worst ? prettyDate(worst.date) : 'no red day'} cls="text-negative" onClick={worst ? () => setSelected(worst.date) : undefined} />
              <Highlight label="Best market" value={topSymbol ? topSymbol.symbol : '—'} sub={topSymbol ? `${formatSignedAmount(topSymbol.net_profit)} · ${topSymbol.trades} trades` : 'trade a little first'} cls="text-primary" />
              <Highlight label="Day streak" value={streak ? `${streak.length} ${streak.green ? 'green' : 'red'}` : '—'} sub="days in a row" cls={streak ? (streak.green ? 'text-positive' : 'text-negative') : 'text-primary'} />
            </div>
          ) : null}

          {selected && account ? <DayTradesPanel iso={selected} account={account} onClose={() => setSelected(null)} /> : null}
        </div>
      </section>
    </div>
  )
}

function Highlight({ label, value, sub, cls, onClick }: { label: string; value: string; sub: string; cls: string; onClick?: () => void }) {
  const body = (
    <>
      <span className="tl-label block">{label}</span>
      <span className={`tl-figure mt-1 block text-[15px] ${cls}`}>{value}</span>
      <span className="block text-xs text-muted">{sub}</span>
    </>
  )
  return onClick ? (
    <div>
      <button type="button" onClick={onClick} className="-m-1.5 rounded-[var(--tl-radius-sm)] p-1.5 text-left hover:bg-surface-elevated">
        {body}
      </button>
    </div>
  ) : (
    <div>{body}</div>
  )
}
