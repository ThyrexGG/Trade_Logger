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

/** Honest provenance strip — demo/seeded data must never look like real data. */
export function ProvenanceBanner({ env }: { env: MacroEnvelope | null }) {
  if (!env) return null
  const demo = env.provenance === 'seed_demo'
  const unavailable = env.provenance === 'unavailable'
  return (
    <div
      className={`rounded-lg border px-3 py-2 text-[11px] ${
        env.provider_is_live
          ? 'border-positive/30 bg-positive/10 text-positive'
          : unavailable
            ? 'border-negative/30 bg-negative/10 text-negative'
            : 'border-warning/30 bg-warning/10 text-warning'
      }`}
    >
      <span className="font-mono font-semibold uppercase">
        {env.provider_is_live ? 'Live data' : unavailable ? 'No data provider' : 'Demo / seeded data'}
      </span>
      <span className="ml-2 text-secondary">
        provider <code>{env.data_provider}</code>
        {demo
          ? ' — realistic shape, NOT live market data. Connect a real macro feed via MACRO_DATA_PROVIDER.'
          : unavailable
            ? ' — every macro response is unavailable until a provider is configured.'
            : ''}
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

      <SectionCard title="Latest important surprises">
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
                    <OpsStatusTag value={s.state} tone={dir(s.direction_bias)} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>
    </div>
  )
}

// --- CALENDAR --------------------------------------------------------
const IMPACTS = ['', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const CCYS = ['', 'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD']

export function MacroCalendar({ data }: { data: MacroEventsResponse }) {
  const [impact, setImpact] = useState('')
  const [ccy, setCcy] = useState('')
  const [q, setQ] = useState('')

  const rows = useMemo(() => {
    const query = q.trim().toLowerCase()
    return data.events.filter((e) => {
      if (impact && e.impact !== impact) return false
      if (ccy && e.currency !== ccy) return false
      if (query && !e.event.toLowerCase().includes(query) && !(e.country ?? '').toLowerCase().includes(query)) return false
      return true
    })
  }, [data.events, impact, ccy, q])

  return (
    <SectionCard
      title="Economic calendar"
      action={<span className="font-mono text-[11px] text-muted">{rows.length} / {data.events.length}</span>}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Event or country…"
          className="w-44 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <select value={ccy} onChange={(e) => setCcy(e.target.value)} className="rounded border border-border bg-background px-2 py-1 text-xs text-primary">
          {CCYS.map((c) => <option key={c} value={c}>{c || 'All currencies'}</option>)}
        </select>
        <select value={impact} onChange={(e) => setImpact(e.target.value)} className="rounded border border-border bg-background px-2 py-1 text-xs text-primary">
          {IMPACTS.map((c) => <option key={c} value={c}>{c || 'All impact'}</option>)}
        </select>
      </div>

      {rows.length === 0 ? (
        <OpsUnavailable>No events match the filters.</OpsUnavailable>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[11px]">
            <thead className="border-b border-border text-muted">
              <tr>
                <th className="px-2 py-1 text-left font-medium">Time</th>
                <th className="px-2 py-1 text-left font-medium">Ccy</th>
                <th className="px-2 py-1 text-left font-medium">Event</th>
                <th className="px-2 py-1 text-left font-medium">Impact</th>
                <th className="px-2 py-1 text-right font-medium">Actual</th>
                <th className="px-2 py-1 text-right font-medium">Forecast</th>
                <th className="px-2 py-1 text-right font-medium">Previous</th>
                <th className="px-2 py-1 text-left font-medium">Surprise</th>
                <th className="px-2 py-1 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 250).map((e) => (
                <tr key={e.event_id} className="border-b border-border-subtle/60">
                  <td className="px-2 py-1 font-mono text-secondary">{e.timestamp?.slice(0, 16).replace('T', ' ') ?? '—'}</td>
                  <td className="px-2 py-1 font-mono text-primary">{e.currency ?? '—'}</td>
                  <td className="px-2 py-1 max-w-[18rem] text-secondary">{e.event}</td>
                  <td className="px-2 py-1"><OpsStatusTag value={e.impact} size="sm" /></td>
                  <td className="px-2 py-1 text-right font-mono tabular-nums text-primary">{num(e.actual, 2)}</td>
                  <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">{num(e.forecast, 2)}</td>
                  <td className="px-2 py-1 text-right font-mono tabular-nums text-muted">{num(e.previous, 2)}</td>
                  <td className="px-2 py-1">
                    {e.surprise.state === 'UNAVAILABLE' ? (
                      <span className="text-muted">—</span>
                    ) : (
                      <span className={dir(e.surprise.direction_bias) === 'positive' ? 'text-positive' : dir(e.surprise.direction_bias) === 'negative' ? 'text-negative' : 'text-muted'}>
                        {e.surprise.normalized_surprise != null ? `${e.surprise.normalized_surprise > 0 ? '+' : ''}${e.surprise.normalized_surprise}` : e.surprise.state.replace('_SURPRISE', '')}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1 font-mono text-muted">{e.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-2 text-[10px] text-muted">
        Surprise = deterministic per-indicator interpretation (not one universal rule). Blank = no
        actual/forecast, or indicator not in the surprise config.
      </p>
    </SectionCard>
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
                        <span className={g.score > 5 ? 'text-positive' : g.score < -5 ? 'text-negative' : 'text-secondary'}>{num(g.score)}</span>
                      </div>
                      <p className="mt-1 text-muted">{g.direction} · {g.confidence}</p>
                      {g.supporting.slice(0, 2).map((s, i) => <p key={i} className="text-positive/80">+ {s}</p>)}
                      {g.conflicting.slice(0, 1).map((s, i) => <p key={i} className="text-negative/80">− {s}</p>)}
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
