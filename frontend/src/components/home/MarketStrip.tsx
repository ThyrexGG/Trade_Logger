import { Link } from 'react-router-dom'
import { getIntelligenceSummary, getOpportunityMap } from '../../api/intelligence'
import { useCachedResource } from '../../lib/dataCache'
import { marketLean, marketMood, usdFromScore, type Tone } from '../../lib/plainEnglish'
import type { OpportunityMapItem } from '../../types/intelligence'

const TONE: Record<Tone, string> = {
  positive: 'text-positive',
  negative: 'text-negative',
  warning: 'text-warning',
  neutral: 'text-secondary',
}
const DOT: Record<Tone, string> = {
  positive: 'bg-positive',
  negative: 'bg-negative',
  warning: 'bg-warning',
  neutral: 'bg-[var(--tl-text-muted)]',
}
const MAX = 6

function arrow(edge: number): string {
  if (edge >= 15) return '↑'
  if (edge <= -15) return '↓'
  return '→'
}

/** Three short bars: how strong a market's lean is (weak / moderate / strong). */
function Meter({ edge }: { edge: number }) {
  const a = Math.abs(edge)
  const lit = a >= 50 ? 3 : a >= 25 ? 2 : a >= 10 ? 1 : 0
  const color = edge >= 0 ? 'bg-positive' : 'bg-negative'
  return (
    <span className="flex items-end gap-[2px]" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span key={i} className={`w-[3px] rounded-[1px] ${i < lit ? color : 'bg-[var(--tl-border)]'}`} style={{ height: `${5 + i * 3}px` }} />
      ))}
    </span>
  )
}

/**
 * Market State — the whole market in one line: the mood, the dollar, which
 * way most markets lean, then the markets themselves with a direction arrow
 * and a three-step strength meter. Markets you actually trade come first.
 * Everything links into Market Intelligence for the full story.
 */
export function MarketStrip({ yourSymbols }: { yourSymbols: string[] }) {
  const summary = useCachedResource('intel:summary', (s) => getIntelligenceSummary(s), { refreshMs: 300_000 })
  const map = useCachedResource('intel:opportunity', (s) => getOpportunityMap(s), { refreshMs: 300_000 })
  const s = summary.data

  const eligible = (map.data?.ranked_assets ?? []).filter((a) => a.ranking_eligible)
  const mine = new Set(yourSymbols.map((x) => x.toUpperCase()))
  const ordered: OpportunityMapItem[] = [
    ...eligible.filter((a) => mine.has(a.symbol.toUpperCase())),
    ...eligible.filter((a) => !mine.has(a.symbol.toUpperCase())).sort((a, b) => Math.abs(b.edge_score) - Math.abs(a.edge_score)),
  ].slice(0, MAX)

  const mood = s ? marketMood(s.primary_regime) : null
  const usd = s ? usdFromScore(s.usd_strength_score) : null
  const loading = (summary.state === 'loading' && !s) || (map.state === 'loading' && !map.data)
  const failed = summary.state === 'error' && !s && map.state === 'error' && !map.data

  return (
    <section className="tl-card flex flex-col gap-3 px-4 py-3 sm:px-5 lg:flex-row lg:items-center lg:gap-6" aria-label="Market state">
      <div className="flex min-w-0 shrink-0 flex-wrap items-center gap-x-5 gap-y-2 lg:flex-nowrap">
        <div className="min-w-0">
          <p className="tl-label">Market</p>
          {loading ? (
            <span className="tl-skeleton mt-1 block h-4 w-40 rounded" />
          ) : mood ? (
            <Link to="/research/intelligence" className="mt-0.5 flex items-center gap-2 text-sm font-medium text-primary hover:text-accent" title={mood.explain}>
              <span className={`h-1.5 w-1.5 rounded-full ${DOT[mood.tone]}`} aria-hidden="true" />
              {mood.label}
            </Link>
          ) : (
            <p className="mt-0.5 text-sm text-muted">{failed ? 'Unavailable right now' : '—'}</p>
          )}
        </div>
        {s ? (
          <>
            <div>
              <p className="tl-label">Leaning</p>
              <p className="mt-0.5 flex items-center gap-2 font-mono text-[12px] text-secondary">
                <span className="flex h-1.5 w-16 overflow-hidden rounded-full bg-[var(--tl-grid-line)]" aria-hidden="true">
                  <span className="bg-positive" style={{ width: `${s.breadth_bullish_pct}%` }} />
                  <span className="bg-[var(--tl-border)]" style={{ width: `${s.breadth_neutral_pct}%` }} />
                  <span className="bg-negative" style={{ width: `${s.breadth_bearish_pct}%` }} />
                </span>
                <span>
                  {Math.round(s.breadth_bullish_pct)}% up · {Math.round(s.breadth_bearish_pct)}% down
                </span>
              </p>
            </div>
            <div>
              <p className="tl-label">US dollar</p>
              <p className="mt-0.5 text-sm text-secondary" title={usd?.explain}>
                {usd?.label}
              </p>
            </div>
          </>
        ) : null}
      </div>

      <span className="hidden h-8 w-px shrink-0 bg-[var(--tl-border-subtle)] lg:block" aria-hidden="true" />

      <ul className="-mx-1 flex min-w-0 flex-1 gap-1 overflow-x-auto px-1 pb-0.5" aria-label="Markets">
        {loading
          ? Array.from({ length: 5 }, (_, i) => (
              <li key={i} className="tl-skeleton h-11 w-28 shrink-0 rounded-[var(--tl-radius)]" />
            ))
          : ordered.map((a) => {
              const lean = marketLean(a.context_state)
              return (
                <li key={a.symbol} className="shrink-0">
                  <Link
                    to={`/research/intelligence/asset/${encodeURIComponent(a.symbol)}`}
                    className="flex min-w-[7rem] flex-col gap-1 rounded-[var(--tl-radius)] px-2.5 py-1.5 transition-colors hover:bg-surface-elevated"
                    title={`${a.symbol}: ${lean.label}${lean.explain ? ` — ${lean.explain}` : ''}`}
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono text-[12.5px] font-medium text-primary">{a.symbol}</span>
                      {mine.has(a.symbol.toUpperCase()) ? <span className="h-1 w-1 rounded-full bg-accent-fill" title="You trade this" /> : null}
                    </span>
                    <span className="flex items-center gap-2">
                      <span className={`font-mono text-[13px] ${TONE[lean.tone]}`}>{arrow(a.edge_score)}</span>
                      <Meter edge={a.edge_score} />
                      <span className="truncate text-[11px] text-muted">{lean.label.split(',')[0]}</span>
                    </span>
                  </Link>
                </li>
              )
            })}
        {!loading && ordered.length === 0 ? <li className="py-2 text-sm text-muted">No market reads available right now.</li> : null}
      </ul>
    </section>
  )
}
