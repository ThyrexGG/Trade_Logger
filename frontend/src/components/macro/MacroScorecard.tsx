import { useState } from 'react'
import { useMacroScorecard } from '../../lib/useMacroScorecard'
import type {
  MacroScorecardCategory,
  MacroScorecardHistoryResponse,
  MacroScorecardIndicator,
  MacroScorecardResponse,
} from '../../types/macro'
import { SectionCard } from '../intelligence/primitives'
import { OpsMetric, OpsStatusTag, OpsUnavailable } from '../operations/primitives'
import { Gauge } from './Gauge'

const INSTRUMENTS = ['XAUUSD', 'USD', 'EUR', 'GBP', 'JPY', 'EURUSD', 'GBPUSD', 'USDJPY', 'EURJPY', 'GBPJPY']
const CATEGORY_LABEL: Record<string, string> = {
  technical: 'Technical Signal',
  cot: 'Institutional Activity (COT)',
  sentiment: 'Sentiment Bias',
  growth: 'Economic Growth',
  jobs: 'Jobs Market',
  inflation: 'Inflation',
}

function tone(dir: string | null | undefined): 'positive' | 'negative' | 'warning' | 'neutral' {
  const s = (dir || '').toUpperCase()
  if (s.includes('BULL')) return 'positive'
  if (s.includes('BEAR')) return 'negative'
  if (s.includes('INSUFFICIENT') || s.includes('MIXED')) return 'warning'
  return 'neutral'
}
function fmt(v: number | null | undefined, d = 2): string {
  return v == null ? '—' : Number(v).toFixed(d)
}
function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return iso.slice(0, 10)
}

/** Blue-above / red-below bar chart of stored composite-score snapshots. */
function ScoreHistory({ data }: { data: MacroScorecardHistoryResponse | null }) {
  if (!data || data.state === 'NO_HISTORY' || data.points.length < 2) {
    return (
      <p className="text-[11px] text-muted">
        {data?.note ??
          'Historical snapshots accumulate over time — no synthetic history is generated. Revisit to build the timeline.'}
      </p>
    )
  }
  const pts = data.points.filter((p) => p.composite_score != null)
  const max = Math.max(10, ...pts.map((p) => Math.abs(p.composite_score as number)))
  return (
    <div>
      <div className="flex h-16 items-center gap-[2px]" aria-label="Composite macro score history">
        {pts.map((p, i) => {
          const v = p.composite_score as number
          const hpct = (Math.abs(v) / max) * 50
          return (
            <div key={i} className="relative flex-1" title={`${fmtDate(p.timestamp)}: ${v > 0 ? '+' : ''}${v}`}>
              <div className="absolute left-0 right-0 top-1/2 h-px bg-border-subtle" />
              <div
                className={`absolute left-0 right-0 ${v >= 0 ? 'bottom-1/2 bg-positive/70' : 'top-1/2 bg-negative/70'}`}
                style={{ height: `${Math.max(2, hpct)}%` }}
              />
            </div>
          )
        })}
      </div>
      <p className="mt-1 text-[10px] text-muted">
        {pts.length} snapshots · {fmtDate(pts[0].timestamp)} → {fmtDate(pts[pts.length - 1].timestamp)}
      </p>
    </div>
  )
}

function IndicatorTable({ rows }: { rows: MacroScorecardIndicator[] }) {
  if (rows.length === 0) return null
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full border-collapse text-[11px]">
        <thead className="border-b border-border-subtle text-muted">
          <tr>
            <th className="py-1 pr-2 text-left font-medium">Indicator</th>
            <th className="py-1 px-1 text-right font-medium">Actual</th>
            <th className="py-1 px-1 text-right font-medium">Forecast</th>
            <th className="py-1 px-1 text-right font-medium">Previous</th>
            <th className="py-1 px-1 text-right font-medium">Surprise</th>
            <th className="py-1 px-1 text-left font-medium">Date</th>
            <th className="py-1 pl-1 text-left font-medium">Read</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const t = tone(r.direction)
            return (
              <tr key={r.indicator} className="border-b border-border-subtle/50">
                <td className="py-1 pr-2 text-secondary">{r.name}</td>
                <td className="py-1 px-1 text-right font-mono tabular-nums text-primary">{fmt(r.actual)}{r.unit === '%' ? '%' : ''}</td>
                <td className="py-1 px-1 text-right font-mono tabular-nums text-secondary">{fmt(r.forecast)}{r.unit === '%' ? '%' : ''}</td>
                <td className="py-1 px-1 text-right font-mono tabular-nums text-muted">{fmt(r.previous)}{r.unit === '%' ? '%' : ''}</td>
                <td
                  className={`py-1 px-1 text-right font-mono tabular-nums ${
                    (r.surprise ?? 0) > 0 ? 'text-positive' : (r.surprise ?? 0) < 0 ? 'text-negative' : 'text-muted'
                  }`}
                >
                  {r.surprise == null ? '—' : `${r.surprise > 0 ? '+' : ''}${fmt(r.surprise)}`}
                </td>
                <td className="py-1 px-1 font-mono text-muted">{fmtDate(r.release_time)}</td>
                <td className="py-1 pl-1">
                  <span
                    className={
                      t === 'positive'
                        ? 'text-positive'
                        : t === 'negative'
                          ? 'text-negative'
                          : 'text-muted'
                    }
                  >
                    {(r.direction || '').split(' ')[0] || '—'}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function CategoryCard({ cat }: { cat: MacroScorecardCategory }) {
  const [open, setOpen] = useState(false)
  const label = CATEGORY_LABEL[cat.category] ?? cat.category
  const insufficient = cat.state === 'INSUFFICIENT_EVIDENCE'
  const rows = cat.indicators ?? []

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex items-center justify-between gap-2 border-b border-border-subtle px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-primary">{label}</p>
          {cat.basis ? <p className="text-[10px] text-muted">{cat.basis}</p> : null}
        </div>
        {insufficient ? (
          <span className="shrink-0 font-mono text-[10px] uppercase text-warning">Insufficient</span>
        ) : (
          <OpsStatusTag value={cat.direction} tone={tone(cat.direction)} size="sm" />
        )}
      </div>

      <div className="flex items-start gap-3 px-3 py-2">
        <Gauge score={cat.gauge} size={72} />
        <div className="min-w-0 flex-1 text-[11px]">
          {insufficient ? (
            <>
              <p className="text-muted">{cat.reason}</p>
              {cat.next_dependency ? (
                <p className="mt-1 text-muted">
                  <span className="text-secondary">Next dependency:</span> {cat.next_dependency}
                </p>
              ) : null}
              {cat.model_prior != null ? (
                <p className="mt-1 text-[10px] text-muted">Model prior (not evidence): {cat.model_prior}</p>
              ) : null}
            </>
          ) : (
            <>
              {(cat.supporting ?? []).slice(0, 3).map((s, i) => (
                <p key={i} className="text-positive/80">+ {s}</p>
              ))}
              {(cat.conflicting ?? []).slice(0, 2).map((s, i) => (
                <p key={i} className="text-negative/80">− {s}</p>
              ))}
              {(cat.context ?? []).map((s, i) => (
                <p key={i} className="text-muted">· {s}</p>
              ))}
              {cat.base && cat.quote ? (
                <p className="text-muted">
                  {cat.base.economy} {cat.base.score} vs {cat.quote.economy} {cat.quote.score}
                </p>
              ) : null}
              {rows.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setOpen((v) => !v)}
                  className="mt-1 text-[11px] text-accent hover:underline"
                >
                  {open ? 'Hide' : `Show ${rows.length}`} indicator{rows.length === 1 ? '' : 's'}
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>

      {open && rows.length > 0 ? <div className="px-3 pb-3">{IndicatorTable({ rows })}</div> : null}
    </div>
  )
}

export function MacroScorecard() {
  const [instrument, setInstrument] = useState('XAUUSD')
  const { scorecard, history, state, error, refetch } = useMacroScorecard(instrument)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-1">
        {INSTRUMENTS.map((i) => (
          <button
            key={i}
            type="button"
            onClick={() => setInstrument(i)}
            className={`rounded border px-2 py-1 font-mono text-[11px] ${
              i === instrument
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-border text-secondary hover:bg-surface-hover'
            }`}
          >
            {i}
          </button>
        ))}
      </div>

      {state === 'loading' ? (
        <div className="rounded-lg border border-border bg-surface p-6 text-center text-xs text-muted">
          Loading {instrument} scorecard…
        </div>
      ) : state === 'error' ? (
        <div className="rounded-lg border border-negative/30 bg-negative/10 p-4 text-xs text-negative">
          {error ?? 'Scorecard unavailable.'}
          <button type="button" onClick={refetch} className="ml-2 underline">
            Retry
          </button>
        </div>
      ) : scorecard ? (
        <ScorecardBody scorecard={scorecard} history={history} />
      ) : null}
    </div>
  )
}

function ScorecardBody({
  scorecard,
  history,
}: {
  scorecard: MacroScorecardResponse
  history: MacroScorecardHistoryResponse | null
}) {
  if (!scorecard.available) {
    return (
      <OpsUnavailable>
        <span className="font-mono uppercase text-warning">{scorecard.state}</span> — {scorecard.reason}
        {scorecard.next_dependency ? (
          <span className="mt-1 block text-muted">Next dependency: {scorecard.next_dependency}</span>
        ) : null}
      </OpsUnavailable>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <SectionCard title={`${scorecard.instrument} · macro bias`}>
          <div className="flex flex-col items-center gap-2">
            <Gauge score={scorecard.gauge} size={140} />
            <OpsStatusTag value={scorecard.bias ?? 'NEUTRAL'} tone={tone(scorecard.bias)} />
            <p className="text-center text-[11px] text-muted">{scorecard.scope_note}</p>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <OpsMetric label="Composite" value={scorecard.composite_score == null ? '—' : `${scorecard.composite_score}`} />
            <OpsMetric label="Confidence" value={scorecard.confidence == null ? '—' : `${scorecard.confidence}`} />
            <OpsMetric label="Eco strength" value={scorecard.economic_strength == null ? '—' : `${scorecard.economic_strength}`} />
            <OpsMetric label="Surprise" value={scorecard.surprise_momentum ?? '—'} />
          </div>
          {scorecard.state !== 'OK' ? (
            <p className="mt-2 rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[10px] text-warning">
              {scorecard.state} — some categories lack provider data (shown below).
            </p>
          ) : null}
        </SectionCard>

        <SectionCard
          title="Score history"
          action={<span className="font-mono text-[10px] text-muted">stored snapshots only</span>}
        >
          <ScoreHistory data={history} />
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(['growth', 'inflation', 'jobs', 'cot'] as const).map((k) => {
              const v = scorecard.sub_scores?.[k]
              return (
                <OpsMetric
                  key={k}
                  label={k}
                  value={v == null ? '—' : `${v}`}
                  tone={v == null ? undefined : v > 5 ? 'positive' : v < -5 ? 'negative' : undefined}
                />
              )
            })}
          </div>
          {scorecard.strongest_category ? (
            <p className="mt-2 text-[11px] text-muted">
              Strongest: <span className="text-positive">{CATEGORY_LABEL[scorecard.strongest_category] ?? scorecard.strongest_category}</span>
              {scorecard.weakest_category ? (
                <>
                  {' '}· Weakest:{' '}
                  <span className="text-negative">{CATEGORY_LABEL[scorecard.weakest_category] ?? scorecard.weakest_category}</span>
                </>
              ) : null}
            </p>
          ) : null}
        </SectionCard>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {scorecard.categories.map((c) => (
          <CategoryCard key={c.category} cat={c} />
        ))}
      </div>

      <p className="border-t border-border-subtle pt-2 text-[10px] text-muted">
        {scorecard.disclaimer} Model {scorecard.model_version}. Surprise interpretation is
        deterministic and family-specific (a hot inflation print is hawkish; a weak jobs print
        is dovish) — not one universal rule.
      </p>
    </div>
  )
}
