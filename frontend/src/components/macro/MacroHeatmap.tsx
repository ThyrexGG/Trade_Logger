import { useState } from 'react'
import { useMacroHeatmap } from '../../lib/useMacroScorecard'
import type { MacroHeatmapResponse } from '../../types/macro'
import { SectionCard } from '../intelligence/primitives'
import { OpsMetric, OpsUnavailable } from '../operations/primitives'
import { ProvenanceBanner } from './MacroViews'

const COUNTRIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD', 'CHF', 'CNY']

function tone(dir: string | null | undefined): 'positive' | 'negative' | 'warning' | 'neutral' {
  const s = (dir || '').toUpperCase()
  if (s.includes('BULL')) return 'positive'
  if (s.includes('BEAR')) return 'negative'
  if (s.includes('INSUFFICIENT')) return 'warning'
  return 'neutral'
}
function fmt(v: number | null | undefined, unit?: string | null): string {
  if (v == null) return '—'
  return `${Number(v).toFixed(2)}${unit === '%' ? '%' : ''}`
}
function impactClass(v?: string): string {
  const s = (v || '').toUpperCase()
  if (s === 'BULLISH') return 'text-positive'
  if (s === 'BEARISH') return 'text-negative'
  return 'text-muted'
}

export function MacroHeatmap() {
  const [country, setCountry] = useState('USD')
  const { index, heatmap, state, error } = useMacroHeatmap(country)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-1">
        {COUNTRIES.map((c) => {
          const meta = index?.countries.find((x) => x.country === c)
          const dim = meta && meta.state === 'INSUFFICIENT_EVIDENCE'
          return (
            <button
              key={c}
              type="button"
              onClick={() => setCountry(c)}
              title={meta ? `${meta.release_count} releases` : undefined}
              className={`rounded border px-2 py-1 font-mono text-[11px] ${
                c === country
                  ? 'border-accent bg-accent/10 text-accent'
                  : dim
                    ? 'border-border-subtle text-muted hover:bg-surface-hover'
                    : 'border-border text-secondary hover:bg-surface-hover'
              }`}
            >
              {c}
            </button>
          )
        })}
      </div>

      {heatmap ? <ProvenanceBanner env={heatmap} /> : null}

      {state === 'loading' ? (
        <div className="rounded-lg border border-border bg-surface p-6 text-center text-xs text-muted">
          Loading {country} economic heatmap…
        </div>
      ) : state === 'error' ? (
        <div className="rounded-lg border border-negative/30 bg-negative/10 p-4 text-xs text-negative">
          {error ?? 'Heatmap unavailable.'}
        </div>
      ) : heatmap ? (
        <HeatmapBody data={heatmap} />
      ) : null}
    </div>
  )
}

function HeatmapBody({ data }: { data: MacroHeatmapResponse }) {
  if (!data.available) {
    return (
      <OpsUnavailable>
        <span className="font-mono uppercase text-warning">{data.state}</span> — {data.reason}
        {data.next_dependency ? (
          <span className="mt-1 block text-muted">Next dependency: {data.next_dependency}</span>
        ) : null}
      </OpsUnavailable>
    )
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <OpsMetric label="Economy" value={`${data.country_name ?? data.country}`} />
        <OpsMetric
          label="Aggregate"
          value={data.aggregate_score == null ? '—' : `${data.aggregate_score}`}
          tone={tone(data.aggregate_direction)}
        />
        <OpsMetric label="Direction" value={data.aggregate_direction ?? '—'} tone={tone(data.aggregate_direction)} />
        <OpsMetric label="Indicators" value={data.indicators.length} />
      </div>

      {data.categories.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {data.categories.map((c) => (
            <span
              key={c.category}
              className="rounded border border-border-subtle px-2 py-1 text-[11px]"
            >
              <span className="text-muted">{c.category}</span>{' '}
              <span
                className={
                  c.score == null
                    ? 'text-warning'
                    : c.score > 5
                      ? 'text-positive'
                      : c.score < -5
                        ? 'text-negative'
                        : 'text-secondary'
                }
              >
                {c.score == null ? 'n/a' : c.score}
              </span>
            </span>
          ))}
        </div>
      ) : null}

      <SectionCard title={`${data.country} economic data`} action={<span className="text-[10px] text-muted">{data.state}</span>}>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[11px]">
            <thead className="border-b border-border text-muted">
              <tr>
                <th className="px-2 py-1 text-left font-medium">Indicator</th>
                <th className="px-2 py-1 text-left font-medium">Date</th>
                <th className="px-2 py-1 text-right font-medium">Surprise</th>
                <th className="px-2 py-1 text-right font-medium">Actual</th>
                <th className="px-2 py-1 text-right font-medium">Forecast</th>
                <th className="px-2 py-1 text-right font-medium">Previous</th>
                <th className="px-2 py-1 text-left font-medium">{data.country} impact</th>
                <th className="px-2 py-1 text-left font-medium">Equity impact</th>
              </tr>
            </thead>
            <tbody>
              {data.indicators.map((r) => (
                <tr key={r.indicator} className="border-b border-border-subtle/50">
                  <td className="px-2 py-1 text-secondary">{r.name}</td>
                  <td className="px-2 py-1 font-mono text-muted">{(r.release_time ?? '').slice(0, 10) || '—'}</td>
                  <td
                    className={`px-2 py-1 text-right font-mono tabular-nums ${
                      (r.surprise ?? 0) > 0 ? 'text-positive' : (r.surprise ?? 0) < 0 ? 'text-negative' : 'text-muted'
                    }`}
                  >
                    {r.surprise == null ? '—' : `${r.surprise > 0 ? '+' : ''}${Number(r.surprise).toFixed(2)}`}
                  </td>
                  <td className="px-2 py-1 text-right font-mono tabular-nums text-primary">{fmt(r.actual, r.unit)}</td>
                  <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">{fmt(r.forecast, r.unit)}</td>
                  <td className="px-2 py-1 text-right font-mono tabular-nums text-muted">{fmt(r.previous, r.unit)}</td>
                  <td className={`px-2 py-1 ${impactClass(r.currency_impact)}`}>{r.currency_impact ?? '—'}</td>
                  <td className={`px-2 py-1 ${impactClass(r.equity_impact)}`}>{r.equity_impact ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[10px] text-muted">
          Impact = deterministic per-indicator interpretation. A hawkish inflation surprise
          supports the currency but pressures equities; strong labour supports both. Not one
          universal rule; never an execution signal.
        </p>
      </SectionCard>

      <p className="text-[10px] text-muted">{data.disclaimer}</p>
    </div>
  )
}
