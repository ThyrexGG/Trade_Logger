import { useMemo, useState } from 'react'
import type {
  MacroAssetsResponse,
  MacroCurrenciesResponse,
  MacroEnvelope,
  MacroEventsResponse,
  MacroOverviewResponse,
} from '../../types/macro'
import { SectionCard } from '../intelligence/primitives'
import { OpsMetric, OpsStatusTag, OpsUnavailable } from '../operations/primitives'
import { ColorLegend, SentimentBadge } from '../common/Sentiment'
import { InfoTip } from '../common/InfoTip'

type ProvEnv = MacroEnvelope

/** Honest provenance strip — demo/seeded data must never look like real data,
 *  and a provider outage must never look like "no evidence". */
export function ProvenanceBanner({ env, quiet = false }: { env: ProvEnv | null; quiet?: boolean }) {
  if (!env) return null
  const st = env.provider_state ?? (env.provider_is_live ? 'LIVE' : env.provenance === 'unavailable' ? 'NONE' : 'SEED_DEMO')
  const live = st === 'LIVE' || st === 'LIVE_STALE'
  const outage = st === 'PROVIDER_UNAVAILABLE' || st === 'PENDING'
  const conflict = st === 'CONFLICT'
  const stale = st === 'STALE' || st === 'LIVE_STALE'
  const status = env.provider_status
  const covRaw = status?.coverage ?? {}
  const cov = Array.isArray(covRaw) ? {} : (covRaw as Record<string, string[]>)
  const covCount = Object.values(cov).reduce((n, m) => n + (m?.length ?? 0), 0)
  const age = status?.hydrated_age_sec
  const nConflicts = env.conflicts?.length ?? 0

  // Embedded under a page that already renders the canonical provenance strip:
  // stay silent while data is nominally live, only surface when there's a caveat.
  if (quiet && live && !stale && !conflict) return null

  const tone = live && !conflict
    ? 'border-positive/30 bg-positive/10 text-positive'
    : outage || st === 'NONE'
      ? 'border-negative/30 bg-negative/10 text-negative'
      : 'border-warning/30 bg-warning/10 text-warning'

  const label = conflict
    ? 'Sources disagree (conflict)'
    : live
      ? stale
        ? 'Live provider data (stale — refresh pending)'
        : 'Live provider data'
      : outage
        ? 'Provider temporarily unavailable'
        : st === 'NONE'
          ? 'No data provider configured'
          : 'Demo / seeded data'

  return (
    <div className={`rounded-lg border px-3 py-2 text-[11px] ${tone}`}>
      <span className="font-mono font-semibold uppercase">{label}</span>
      <span className="ml-2 text-secondary">
        provider <code>{env.data_provider}</code>
        {conflict ? (
          <>
            {' '}— {nConflicts} indicator{nConflicts === 1 ? '' : 's'} where two sources disagree.
            Showing the higher-precedence source; see the Providers panel. Nothing is averaged.
          </>
        ) : live ? (
          <>
            {' '}· {covCount} live series across {Object.keys(cov).length} economies
            {age != null ? ` · updated ${Math.round(age / 60)} min ago` : ''}
            {' '}· consensus forecast{env.forecast_status?.configured ? '' : ' not configured'} (surprise
            {env.forecast_status?.configured ? '' : ' = n/a'})
            {env.calendar_status && (env.calendar_status.events_cached ?? 0) > 0
              ? ` · calendar: ${env.calendar_status.provider} (${env.calendar_status.scheduled_ahead ?? 0} ahead)`
              : ''}
            {env.cot_status?.provider_state === 'LIVE' ? ' · COT: CFTC live' : ''}
          </>
        ) : outage ? (
          <> — last-good data shown where available; this is NOT "insufficient evidence".{status?.last_error ? ` (${status.last_error})` : ''}</>
        ) : st === 'NONE' ? (
          ' — every macro response is unavailable until a provider is configured.'
        ) : (
          ' — realistic shape, NOT live market data. Set MACRO_DATA_PROVIDER=fred + FRED_API_KEY for real data.'
        )}
      </span>
    </div>
  )
}

function dir(v: string | null | undefined): 'positive' | 'negative' | 'warning' | 'neutral' {
  const s = (v || '').toUpperCase()
  if (s.includes('BULL') || s === 'POSITIVE') return 'positive'
  if (s.includes('BEAR') || s === 'NEGATIVE') return 'negative'
  if (s.includes('MIXED') || s.includes('HAWK') || s.includes('DOV')) return 'warning'
  return 'neutral'
}
function num(v: number | null | undefined, d = 1): string {
  return v == null ? '—' : v.toFixed(d)
}

// --- OVERVIEW ---------------------------------------------------------
export function MacroOverview({ data }: { data: MacroOverviewResponse }) {
  if (!data.available) {
    return <OpsUnavailable>No macro data available from the current provider.</OpsUnavailable>
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <OpsMetric label="Macro regime" value={data.macro_regime} sub={data.macro_regime_note ?? undefined} />
        <OpsMetric label="Confidence" value={data.confidence != null ? `${data.confidence}` : '—'} />
        <OpsMetric label="High-impact ahead" value={data.upcoming_high_impact.length} />
        <OpsMetric label="Recent surprises" value={data.latest_surprises.length} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Strongest currencies">
          {data.strongest_currencies.length === 0 ? (
            <OpsUnavailable>Insufficient currency macro evidence.</OpsUnavailable>
          ) : (
            <ul className="space-y-1 text-xs">
              {data.strongest_currencies.map((c) => (
                <li key={c.currency} className="flex justify-between">
                  <span className="font-mono text-primary">{c.currency}</span>
                  <span className="font-mono text-positive">{num(c.score)}</span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
        <SectionCard title="Weakest currencies">
          {data.weakest_currencies.length === 0 ? (
            <OpsUnavailable>Insufficient currency macro evidence.</OpsUnavailable>
          ) : (
            <ul className="space-y-1 text-xs">
              {data.weakest_currencies.map((c) => (
                <li key={c.currency} className="flex justify-between">
                  <span className="font-mono text-primary">{c.currency}</span>
                  <span className="font-mono text-negative">{num(c.score)}</span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>

      {data.insufficient_currencies.length > 0 ? (
        <p className="rounded border border-border-subtle px-2 py-1 text-[11px] text-muted">
          Insufficient evidence (no releases from provider): {data.insufficient_currencies.join(', ')}
        </p>
      ) : null}

      <SectionCard title="Upcoming high-impact events">
        {data.upcoming_high_impact.length === 0 ? (
          <OpsUnavailable>No high-impact events in the forward window.</OpsUnavailable>
        ) : (
          <ul className="space-y-1 text-[11px]">
            {data.upcoming_high_impact.map((e) => (
              <li key={e.event_id} className="flex flex-wrap items-center gap-2">
                <OpsStatusTag value={e.impact} size="sm" />
                <span className="font-mono text-muted">{e.currency}</span>
                <span className="text-primary">{e.event}</span>
                <span className="font-mono text-muted">{e.timestamp?.slice(0, 16).replace('T', ' ')}</span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard
        title="Latest important surprises"
        action={
          <InfoTip text="Surprise = actual release vs consensus forecast, read for its effect on the currency (a hot inflation print is currency-positive/hawkish; a weak jobs print is currency-negative/dovish). Not one universal rule.">
            <span className="text-[10px] text-muted">what is this</span>
          </InfoTip>
        }
      >
        {data.latest_surprises.length === 0 ? (
          <OpsUnavailable>No scored surprises available.</OpsUnavailable>
        ) : (
          <table className="w-full border-collapse text-[11px]">
            <tbody>
              {data.latest_surprises.map((s, i) => (
                <tr key={i} className="border-b border-border-subtle/60">
                  <td className="py-1 font-mono text-muted">{s.currency}</td>
                  <td className="py-1 text-primary">{s.event}</td>
                  <td className="py-1 text-right font-mono tabular-nums text-secondary">
                    {num(s.actual, 2)} vs {num(s.forecast, 2)}
                  </td>
                  <td className="py-1 text-right">
                    <SentimentBadge
                      value={s.direction_bias}
                      label={s.state.replace(/_/g, ' ').replace(' SURPRISE', '')}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <ColorLegend className="mt-2" />
      </SectionCard>
    </div>
  )
}

// --- CALENDAR --------------------------------------------------------
const IMPACTS = ['', 'LOW', 'MEDIUM', 'HIGH']
const CCYS = ['', 'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD', 'CNY']

/** ForexFactory-style compact number: 214K, 3.2B, -0.4%, 56.5. */
function fmtVal(v: number | null | undefined, unit: string | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return ''
  const abs = Math.abs(v)
  const pct = (unit ?? '').includes('%')
  let s: string
  if (abs >= 1e9) s = `${(v / 1e9).toFixed(abs >= 1e11 ? 0 : 1)}B`
  else if (abs >= 1e6) s = `${(v / 1e6).toFixed(1)}M`
  else if (abs >= 1e4) s = `${Math.round(v / 1e3)}K`
  else if (Number.isInteger(v)) s = String(v)
  else s = v.toFixed(abs < 10 ? (pct ? 1 : 2) : 1)
  return pct ? `${s}%` : s
}

function impactBar(impact: string): string {
  const s = impact.toUpperCase()
  if (s === 'HIGH' || s === 'CRITICAL') return 'bg-negative'
  if (s === 'MEDIUM') return 'bg-warning'
  return 'bg-warning/35'
}

function dayKey(iso: string | null): string {
  return (iso ?? '').slice(0, 10)
}
function dayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}
function evTime(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function MacroCalendar({ data }: { data: MacroEventsResponse }) {
  const [impact, setImpact] = useState('')
  const [ccy, setCcy] = useState('')
  const [q, setQ] = useState('')
  const [releasedOnly, setReleasedOnly] = useState(false)

  const rows = useMemo(() => {
    const query = q.trim().toLowerCase()
    return data.events
      .filter((e) => {
        if (impact && e.impact !== impact) return false
        if (ccy && e.currency !== ccy) return false
        if (releasedOnly && e.actual == null) return false
        if (query && !e.event.toLowerCase().includes(query) && !(e.currency ?? '').toLowerCase().includes(query)) return false
        return true
      })
      .slice()
      .sort((a, b) => (a.timestamp ?? '').localeCompare(b.timestamp ?? ''))
  }, [data.events, impact, ccy, q, releasedOnly])

  const groups = useMemo(() => {
    const m = new Map<string, typeof rows>()
    for (const e of rows) {
      const k = dayKey(e.timestamp)
      if (!m.has(k)) m.set(k, [])
      m.get(k)!.push(e)
    }
    return [...m.entries()]
  }, [rows])

  const todayKey = new Date().toISOString().slice(0, 10)
  const cal = data.calendar

  const selectClass = 'rounded border border-border bg-background px-2 py-1 text-xs text-primary'

  return (
    <SectionCard
      title="Economic calendar"
      action={
        <span className="font-mono text-[11px] text-muted">
          {cal?.calendar_source ?? data.data_provider} · {rows.length} events
        </span>
      }
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Event or currency…"
          className="w-40 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <select value={ccy} onChange={(e) => setCcy(e.target.value)} className={selectClass}>
          {CCYS.map((c) => <option key={c} value={c}>{c || 'All currencies'}</option>)}
        </select>
        <select value={impact} onChange={(e) => setImpact(e.target.value)} className={selectClass}>
          {IMPACTS.map((c) => <option key={c} value={c}>{c || 'All impact'}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-[11px] text-secondary">
          <input type="checkbox" checked={releasedOnly} onChange={(e) => setReleasedOnly(e.target.checked)} />
          Released only
        </label>
      </div>

      {cal?.calendar_source === 'ForexFactory' ? (
        <p className="mb-2 text-[10px] text-muted">
          ForexFactory publishes the current week only; past weeks are kept as they roll off
          (rolling ~75 days). For instant multi-week history with actuals, set{' '}
          <span className="font-mono text-secondary">FMP_API_KEY</span> in <span className="font-mono">.env</span>.
        </p>
      ) : null}

      {rows.length === 0 ? (
        <OpsUnavailable>
          {cal?.calendar_state === 'PROVIDER_UNAVAILABLE'
            ? 'The calendar source is temporarily unreachable. It will fill back in on the next refresh.'
            : 'No events match the filters (the ForexFactory feed only covers the current week — set FMP_API_KEY for multi-week history).'}
        </OpsUnavailable>
      ) : (
        <div className="max-h-[70vh] overflow-auto rounded border border-border-subtle">
          <table className="w-full min-w-[34rem] border-collapse text-[11px]">
            <thead className="sticky top-0 z-10 bg-surface-elevated text-[10px] uppercase tracking-wide text-muted">
              <tr>
                <th className="px-2 py-1.5 text-left font-medium">Time</th>
                <th className="px-1 py-1.5 text-left font-medium">Ccy</th>
                <th className="px-1 py-1.5 font-medium" />
                <th className="px-2 py-1.5 text-left font-medium">Event</th>
                <th className="px-3 py-1.5 text-right font-medium">Actual</th>
                <th className="px-3 py-1.5 text-right font-medium">Forecast</th>
                <th className="px-3 py-1.5 text-right font-medium">Previous</th>
              </tr>
            </thead>
            <tbody>
              {groups.map(([day, evs]) => (
                <DayGroup key={day} day={day} evs={evs} isToday={day === todayKey} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-2 space-y-1">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-muted">
          <span className="font-medium uppercase tracking-wide">Impact</span>
          <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-1 rounded-sm bg-negative" /> high</span>
          <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-1 rounded-sm bg-warning" /> medium</span>
          <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-1 rounded-sm bg-warning/35" /> low</span>
          <span>· 🎤 speech · Holiday = market closed</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-muted">
          <span className="font-medium uppercase tracking-wide">Actual</span>
          <span className="text-positive">▲ green = beat / good for the currency</span>
          <span className="text-negative">▼ red = miss</span>
          <span>· ▲▼ next to Previous = data was revised</span>
          {cal?.last_refresh_utc ? <span>· refreshed {new Date(cal.last_refresh_utc).toLocaleString()}</span> : null}
        </div>
      </div>
    </SectionCard>
  )
}

function DayGroup({
  day,
  evs,
  isToday,
}: {
  day: string
  evs: MacroEventsResponse['events']
  isToday: boolean
}) {
  return (
    <>
      {evs.map((e, i) => {
        const kind = e.kind ?? (e.impact.toUpperCase() === 'HOLIDAY' ? 'holiday' : 'release')
        const bias = dir(e.surprise?.direction_bias)
        const actualTone =
          e.actual == null ? 'text-secondary'
          : bias === 'positive' ? 'text-positive'
          : bias === 'negative' ? 'text-negative'
          : 'text-primary'
        const arrow = e.actual != null && bias === 'positive' ? '▲' : e.actual != null && bias === 'negative' ? '▼' : ''
        const revUp = e.revised_previous != null && e.previous != null && e.revised_previous > e.previous
        const revDown = e.revised_previous != null && e.previous != null && e.revised_previous < e.previous
        const high = e.impact.toUpperCase() === 'HIGH' || e.impact.toUpperCase() === 'CRITICAL'

        const dayCell =
          i === 0 ? (
            <td
              rowSpan={evs.length}
              className={`whitespace-nowrap border-r border-border-subtle px-2 py-1 align-top text-[10px] font-semibold ${
                isToday ? 'text-accent' : 'text-secondary'
              }`}
            >
              {dayLabel(day)}
            </td>
          ) : null

        const timeCell = (
          <td className="whitespace-nowrap px-2 py-1 font-mono text-[10px] text-muted">{evTime(e.timestamp)}</td>
        )
        const ccyCell = (
          <td className="px-1 py-1 font-mono text-[11px] font-semibold text-primary">
            {e.currency ?? <span className="text-muted" title="Global / multi-country">🌐</span>}
          </td>
        )

        if (kind === 'holiday') {
          return (
            <tr key={e.event_id} className="border-t border-border-subtle/50 bg-surface-elevated/30 text-muted">
              {dayCell}
              {timeCell}
              {ccyCell}
              <td className="px-1 py-1" />
              <td className="px-2 py-1" colSpan={4}>
                <span className="rounded bg-surface-elevated px-1.5 py-0.5 text-[9px] uppercase tracking-wide">Holiday</span>{' '}
                <span className="italic">{e.event}</span>
                <span className="ml-1 text-[10px]">— market closed / thin liquidity</span>
              </td>
            </tr>
          )
        }

        if (kind === 'speech') {
          return (
            <tr key={e.event_id} className={`border-t border-border-subtle/50 ${high ? 'bg-negative/[0.04]' : ''} hover:bg-surface-hover/50`}>
              {dayCell}
              {timeCell}
              {ccyCell}
              <td className="px-1 py-1">
                <span className={`inline-block h-3 w-1 rounded-sm ${impactBar(e.impact)}`} title={e.impact} />
              </td>
              <td className={`px-2 py-1 ${high ? 'font-medium text-primary' : 'text-secondary'}`} colSpan={4}>
                <span aria-hidden="true">🎤</span> {e.event}
              </td>
            </tr>
          )
        }

        return (
          <tr
            key={e.event_id}
            className={`border-t border-border-subtle/50 ${high ? 'bg-negative/[0.04]' : ''} hover:bg-surface-hover/50`}
          >
            {dayCell}
            {timeCell}
            {ccyCell}
            <td className="px-1 py-1">
              <span className={`inline-block h-3 w-1 rounded-sm ${impactBar(e.impact)}`} title={e.impact} />
            </td>
            <td className={`px-2 py-1 ${high ? 'font-medium text-primary' : 'text-secondary'}`}>{e.event}</td>
            <td className={`px-3 py-1 text-right font-mono tabular-nums ${actualTone}`}>
              {e.actual != null ? (
                <>
                  {fmtVal(e.actual, e.unit)}
                  {arrow ? <span className="ml-0.5 text-[9px]">{arrow}</span> : null}
                </>
              ) : (
                <span className="text-muted">—</span>
              )}
            </td>
            <td className="px-3 py-1 text-right font-mono tabular-nums text-muted">
              {e.forecast != null ? fmtVal(e.forecast, e.unit) : '—'}
            </td>
            <td className="px-3 py-1 text-right font-mono tabular-nums text-muted">
              {e.previous != null ? (
                <>
                  {fmtVal(e.previous, e.unit)}
                  {revUp ? <span className="ml-0.5 text-[9px] text-positive">▲</span> : null}
                  {revDown ? <span className="ml-0.5 text-[9px] text-negative">▼</span> : null}
                </>
              ) : (
                '—'
              )}
            </td>
          </tr>
        )
      })}
    </>
  )
}

// --- CURRENCIES -----------------------------------------------------
export function MacroCurrencies({ data }: { data: MacroCurrenciesResponse }) {
  return (
    <div className="space-y-3">
      {data.currencies.map((c) => (
        <SectionCard
          key={c.currency}
          title={c.currency}
          action={
            c.available
              ? <OpsStatusTag value={c.direction ?? 'NEUTRAL'} tone={dir(c.direction)} size="sm" />
              : <span className="font-mono text-[11px] text-warning">{c.state}</span>
          }
        >
          {!c.available ? (
            <OpsUnavailable>{c.reason ?? 'Insufficient evidence.'}</OpsUnavailable>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <OpsMetric label="Macro score" value={num(c.score)} tone={dir(c.direction)} />
                <OpsMetric label="Classification" value={c.classification ?? '—'} />
                <OpsMetric label="Confidence" value={c.confidence != null ? `${c.confidence}` : '—'} />
                <OpsMetric label="Surprise momentum" value={c.surprise_momentum ?? '—'} sub={c.surprise_score != null ? num(c.surprise_score) : undefined} />
              </div>
              {c.factor_groups ? (
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(c.factor_groups).map(([name, g]) => (
                    <div key={name} className="rounded border border-border-subtle bg-surface-elevated/30 px-2.5 py-2 text-[11px]">
                      <div className="flex justify-between">
                        <span className="font-mono text-muted">{name}</span>
                        <span className={(g.score ?? 0) > 5 ? 'text-positive' : (g.score ?? 0) < -5 ? 'text-negative' : 'text-secondary'}>{num(g.score)}</span>
                      </div>
                      <p className="mt-1 text-muted">{g.state === 'INSUFFICIENT_EVIDENCE' ? (g.reason ?? 'Insufficient evidence') : `${g.direction} · ${g.confidence}`}</p>
                      {(g.supporting ?? []).slice(0, 2).map((s, i) => <p key={i} className="text-positive/80">+ {s}</p>)}
                      {(g.conflicting ?? []).slice(0, 1).map((s, i) => <p key={i} className="text-negative/80">− {s}</p>)}
                    </div>
                  ))}
                </div>
              ) : null}
            </>
          )}
        </SectionCard>
      ))}
    </div>
  )
}

// --- ASSETS -------------------------------------------------------
export function MacroAssets({ data }: { data: MacroAssetsResponse }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {data.assets.map((a) => (
        <SectionCard
          key={a.asset}
          title={`${a.label ?? a.asset} (${a.asset})`}
          action={
            a.available
              ? <OpsStatusTag value={a.macro_bias ?? 'NEUTRAL'} tone={dir(a.macro_bias)} size="sm" />
              : <span className="font-mono text-[11px] text-warning">{a.state}</span>
          }
        >
          {!a.available ? (
            <OpsUnavailable>{a.reason ?? 'Insufficient evidence.'}</OpsUnavailable>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2">
                <OpsMetric label="Macro bias" value={a.macro_bias ?? '—'} tone={dir(a.macro_bias)} />
                <OpsMetric label="Score" value={num(a.score)} />
                <OpsMetric label="Confidence" value={a.confidence != null ? `${a.confidence}` : '—'} />
                <OpsMetric label="Evidence" value={a.evidence_count ?? 0} />
              </div>
              {(a.supporting_factors?.length ?? 0) > 0 ? (
                <div className="mt-2 text-[11px]">
                  <p className="text-muted">Supporting</p>
                  {a.supporting_factors!.map((f, i) => (
                    <p key={i} className="text-positive/80">+ {f.factor} ({num(f.score)}) {f.note ? `— ${f.note}` : ''}</p>
                  ))}
                </div>
              ) : null}
              {(a.opposing_factors?.length ?? 0) > 0 ? (
                <div className="mt-2 text-[11px]">
                  <p className="text-muted">Opposing</p>
                  {a.opposing_factors!.map((f, i) => (
                    <p key={i} className="text-negative/80">− {f.factor} ({num(f.score)}) {f.note ? `— ${f.note}` : ''}</p>
                  ))}
                </div>
              ) : null}
              {a.method ? <p className="mt-2 text-[10px] text-muted">{a.method}</p> : null}
            </>
          )}
        </SectionCard>
      ))}
    </div>
  )
}
