import { useState } from 'react'
import { useMacroScorecard } from '../../lib/useMacroScorecard'
import type {
  MacroScorecardCategory,
  MacroScorecardHistoryResponse,
  MacroScorecardIndicator,
  MacroScorecardResponse,
} from '../../types/macro'
import { SectionCard } from '../intelligence/primitives'
import { SentimentBadge, SentimentText } from '../common/Sentiment'
import { InfoTip } from '../common/InfoTip'
import { classifySentiment, toneText } from '../../lib/sentiment'
import { Gauge } from './Gauge'
import { ProvenanceBanner } from './MacroViews'

const INSTRUMENTS = ['XAUUSD', 'USD', 'EUR', 'GBP', 'JPY', 'EURUSD', 'GBPUSD', 'USDJPY', 'EURJPY', 'GBPJPY']

const CATEGORY_LABEL: Record<string, string> = {
  technical: 'Technicals',
  cot: 'Institutional activity (COT)',
  sentiment: 'Crowd sentiment',
  growth: 'Economic growth',
  jobs: 'Jobs market',
  inflation: 'Inflation',
}
const CATEGORY_INFO: Record<string, string> = {
  technical: 'Chart trend + seasonality read. Needs a macro-technical provider — the per-instrument chart on the Market page is separate.',
  cot: "CFTC Commitments of Traders — how large speculators are positioned. Needs MACRO_COT_PROVIDER=cftc.",
  sentiment: 'Retail / crowd positioning from a broker feed. No free redistributable source is configured.',
  growth: 'GDP, PMIs, retail sales, consumer confidence — the pace of the economy vs forecast.',
  jobs: 'Payrolls, unemployment rate, jobless claims — labour-market strength vs forecast.',
  inflation: 'CPI / PPI / PCE and the policy-rate read — hotter than forecast is hawkish (currency-positive).',
}

const MOMENTUM_LABEL: Record<string, string> = {
  INLINE: 'in line with forecasts',
  'INLINE MACRO DATASTREAM': 'in line with forecasts',
  NEUTRAL: 'neutral',
  'STRONG POSITIVE SURPRISE REGIME': 'data strongly beating forecasts',
  'MODERATE POSITIVE SURPRISES': 'data beating forecasts',
  'STRONG DOWNSIDE SURPRISE REGIME': 'data strongly missing forecasts',
  'MODERATE DOWNSIDE SURPRISES': 'data missing forecasts',
  HAWKISH: 'hawkish tilt',
  DOVISH: 'dovish tilt',
}
const momentumText = (v: string | null | undefined) =>
  !v ? '—' : MOMENTUM_LABEL[v.toUpperCase().trim()] ?? v.replace(/_/g, ' ').toLowerCase()

const fmt = (v: number | null | undefined, unit?: string | null) => {
  if (v == null) return '—'
  const s = Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : Number(v).toFixed(Math.abs(v) < 10 ? 2 : 1)
  return unit === '%' ? `${s}%` : s
}
const fmtDate = (iso: string | null | undefined) =>
  !iso ? '—' : new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

const catScore = (c: MacroScorecardCategory): number | null =>
  c.score ?? c.gauge ?? null

// --- left rail ----------------------------------------------------------
function ScoreBar({ label, score }: { label: string; score: number | null }) {
  const s = score ?? 0
  const pct = Math.min(100, (Math.abs(s) / 10) * 100)
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-28 shrink-0 text-secondary">{label}</span>
      <div className="relative h-3.5 flex-1 rounded bg-surface-elevated/50">
        <div className="absolute inset-y-0 left-1/2 w-px bg-border" />
        {score != null ? (
          <div
            className={`absolute inset-y-0 rounded ${s >= 0 ? 'left-1/2 bg-positive/60' : 'right-1/2 bg-negative/60'}`}
            style={{ width: `${pct / 2}%` }}
          />
        ) : null}
      </div>
      <span
        className={`w-8 shrink-0 text-right font-mono tabular-nums ${
          score == null ? 'text-muted' : s > 0 ? 'text-positive' : s < 0 ? 'text-negative' : 'text-secondary'
        }`}
      >
        {score == null ? '—' : `${s > 0 ? '+' : ''}${Math.round(s)}`}
      </span>
    </div>
  )
}

function MiniHistory({ data }: { data: MacroScorecardHistoryResponse | null }) {
  const pts = (data?.points ?? []).filter((p) => p.composite_score != null)
  if (pts.length < 3) {
    return (
      <p className="text-[10px] text-muted">
        History builds up as you revisit — {pts.length} snapshot{pts.length === 1 ? '' : 's'} so far, no synthetic backfill.
      </p>
    )
  }
  const max = Math.max(4, ...pts.map((p) => Math.abs(p.composite_score as number)))
  return (
    <div>
      <div className="flex h-10 items-center gap-px" aria-label="composite score history">
        {pts.map((p, i) => {
          const v = p.composite_score as number
          const h = (Math.abs(v) / max) * 45
          return (
            <div key={i} className="relative flex-1" title={`${p.timestamp.slice(0, 10)}: ${v > 0 ? '+' : ''}${v}`}>
              <div className="absolute inset-x-0 top-1/2 h-px bg-border-subtle" />
              <div
                className={`absolute inset-x-0 ${v >= 0 ? 'bottom-1/2 bg-positive/70' : 'top-1/2 bg-negative/70'}`}
                style={{ height: `${Math.max(2, h)}%` }}
              />
            </div>
          )
        })}
      </div>
      <p className="mt-1 text-[10px] text-muted">
        {pts.length} snapshots · {pts[0].timestamp.slice(0, 10)} → {pts[pts.length - 1].timestamp.slice(0, 10)}
      </p>
    </div>
  )
}

function Rail({
  sc,
  history,
}: {
  sc: MacroScorecardResponse
  history: MacroScorecardHistoryResponse | null
}) {
  const verdict = classifySentiment(sc.bias)
  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="border-b border-border-subtle px-3 py-2">
        <p className="text-[10px] uppercase tracking-wider text-muted">{sc.instrument} · macro bias</p>
        <p className={`text-xl font-semibold ${toneText(verdict.tone)}`}>
          {sc.bias ? sc.bias.replace(/_/g, ' ') : 'Neutral'}
        </p>
      </div>

      <div className="flex flex-col items-center gap-1 px-3 py-3">
        <Gauge score={sc.gauge} size={150} />
        {sc.confidence != null ? (
          <span className="text-[10px] text-muted">
            confidence{' '}
            <InfoTip text="How sure the model is, given how much provider data each category actually has. Low = thin evidence.">
              <span className="text-secondary">{sc.confidence}/100</span>
            </InfoTip>
          </span>
        ) : null}
        {sc.surprise_momentum ? (
          <span className="text-[10px] text-muted">
            recent data:{' '}
            <SentimentText
              value={sc.surprise_momentum}
              label={momentumText(sc.surprise_momentum)}
              hint="flat"
              arrow={false}
            />
          </span>
        ) : null}
      </div>

      <div className="space-y-1.5 border-t border-border-subtle px-3 py-3">
        <ScoreBar label="Macro composite" score={sc.composite_score} />
        {sc.categories.map((c) => (
          <ScoreBar key={c.category} label={CATEGORY_LABEL[c.category] ?? c.category} score={catScore(c)} />
        ))}
      </div>

      <div className="border-t border-border-subtle px-3 py-3">
        <p className="mb-1 text-[10px] uppercase tracking-wider text-muted">Score history</p>
        <MiniHistory data={history} />
      </div>
    </div>
  )
}

// --- right side: category tables --------------------------------------
const SHOWN = 6

function CategoryBlock({ cat }: { cat: MacroScorecardCategory }) {
  const [open, setOpen] = useState(false)
  const label = CATEGORY_LABEL[cat.category] ?? cat.category
  const insufficient = cat.state === 'INSUFFICIENT_EVIDENCE'

  const rows = [...(cat.indicators ?? [])].sort((a, b) =>
    (b.release_time ?? '').localeCompare(a.release_time ?? ''),
  )
  const hasForecast = rows.some((r) => r.forecast != null)
  const visible = open ? rows : rows.slice(0, SHOWN)

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="flex items-center justify-between gap-2 bg-surface-elevated/60 px-3 py-1.5">
        <span className="flex items-center text-xs font-semibold uppercase tracking-wide text-secondary">
          {label}
          {CATEGORY_INFO[cat.category] ? <InfoTip text={CATEGORY_INFO[cat.category]} /> : null}
        </span>
        {insufficient ? (
          <span className="font-mono text-[10px] uppercase text-muted">no data</span>
        ) : (
          <SentimentBadge value={cat.direction} />
        )}
      </div>

      {insufficient ? (
        <div className="px-3 py-2 text-[11px] text-muted">
          {cat.reason}
          {cat.next_dependency ? (
            <span className="mt-1 block">
              <span className="text-secondary">To enable:</span> {cat.next_dependency}
            </span>
          ) : null}
          {cat.model_prior != null ? (
            <span className="mt-1 block text-[10px]">
              Model's default assumption without data: {cat.model_prior}/100 — not counted in the score.
            </span>
          ) : null}
        </div>
      ) : rows.length === 0 ? (
        <div className="px-3 py-2 text-[11px] text-muted">
          {(cat.context ?? []).join(' · ') || 'No individual releases in the window.'}
        </div>
      ) : (
        <>
          <table className="w-full text-[11px]">
            <thead className="text-[10px] uppercase tracking-wide text-muted">
              <tr className="border-b border-border-subtle">
                <th className="px-3 py-1 text-left font-medium">Indicator</th>
                <th className="px-2 py-1 text-left font-medium">Read</th>
                <th className="px-2 py-1 text-right font-medium">Latest</th>
                <th className="px-2 py-1 text-right font-medium">
                  {hasForecast ? 'Forecast' : 'Previous'}
                </th>
                {hasForecast ? (
                  <th className="px-2 py-1 text-right font-medium">
                    <InfoTip text="Actual minus forecast, read for direction. Green if it favours the currency, red if against.">
                      Surprise
                    </InfoTip>
                  </th>
                ) : null}
                <th className="px-3 py-1 text-right font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r: MacroScorecardIndicator) => (
                <tr key={r.indicator} className="border-b border-border-subtle/40 last:border-0">
                  <td className="px-3 py-1 text-secondary">{r.name}</td>
                  <td className="px-2 py-1">
                    {r.direction ? (
                      <SentimentText value={r.direction} label={(r.direction || '').split(' ')[0]} />
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="px-2 py-1 text-right font-mono tabular-nums text-primary">{fmt(r.actual, r.unit)}</td>
                  <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">
                    {fmt(hasForecast ? r.forecast : r.previous, r.unit)}
                  </td>
                  {hasForecast ? (
                    <td className="px-2 py-1 text-right font-mono tabular-nums">
                      {r.surprise == null ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <SentimentText value={r.surprise} label={`${r.surprise > 0 ? '+' : ''}${fmt(r.surprise)}`} arrow={false} />
                      )}
                    </td>
                  ) : null}
                  <td className="px-3 py-1 text-right font-mono text-muted">{fmtDate(r.release_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > SHOWN ? (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="w-full border-t border-border-subtle px-3 py-1 text-left text-[10px] text-accent hover:bg-surface-hover"
            >
              {open ? 'Show fewer' : `Show all ${rows.length} indicators`}
            </button>
          ) : null}
        </>
      )}

      {!insufficient && (cat.supporting?.length || cat.conflicting?.length) ? (
        <div className="space-y-0.5 border-t border-border-subtle px-3 py-1.5 text-[10px]">
          {(cat.supporting ?? []).slice(0, 3).map((s, i) => (
            <p key={`s${i}`} className="text-positive/80">+ {s}</p>
          ))}
          {(cat.conflicting ?? []).slice(0, 2).map((s, i) => (
            <p key={`c${i}`} className="text-negative/80">− {s}</p>
          ))}
        </div>
      ) : null}

      {!insufficient && !hasForecast && rows.length > 0 ? (
        <p className="border-t border-border-subtle px-3 py-1 text-[9px] text-muted">
          No consensus-forecast feed configured, so "Read" reflects the level and trend, not a beat/miss.
        </p>
      ) : null}
    </div>
  )
}

// --- page -------------------------------------------------------------
export function MacroScorecard() {
  const [instrument, setInstrument] = useState('XAUUSD')
  const { scorecard, history, state, error, refetch } = useMacroScorecard(instrument)

  return (
    <div className="space-y-3">
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

      {scorecard ? <ProvenanceBanner env={scorecard} /> : null}

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
      ) : scorecard && !scorecard.available ? (
        <SectionCard title={`${scorecard.instrument} macro`} info="One directional lean for this instrument from a weighted blend of growth / inflation / jobs / positioning.">
          <p className="text-xs text-warning">
            {scorecard.state} — {scorecard.reason}
          </p>
          {scorecard.next_dependency ? (
            <p className="mt-1 text-[11px] text-muted">To enable: {scorecard.next_dependency}</p>
          ) : null}
        </SectionCard>
      ) : scorecard ? (
        <>
          <p className="text-xs text-secondary">
            {scorecard.instrument} macro read:{' '}
            <SentimentText value={scorecard.bias} label={(scorecard.bias ?? 'neutral').replace(/_/g, ' ').toLowerCase()} />
            {scorecard.confidence != null ? ` · confidence ${scorecard.confidence}/100` : ''}
            {'  '}
            <InfoTip text="Blend of the category scores below. Green categories push the read bullish, red push it bearish. A category with no data provider ('no data') is not counted — it's missing, not neutral." />
          </p>

          <div className="grid gap-3 lg:grid-cols-[300px_1fr] lg:items-start">
            <Rail sc={scorecard} history={history} />
            <div className="space-y-3">
              {scorecard.categories.map((c) => (
                <CategoryBlock key={c.category} cat={c} />
              ))}
            </div>
          </div>

          <p className="border-t border-border-subtle pt-2 text-[10px] text-muted">
            {scorecard.disclaimer} Model {scorecard.model_version}. Surprise interpretation is deterministic
            and family-specific (a hot inflation print is hawkish; a weak jobs print is dovish) — not one
            universal rule.
          </p>
        </>
      ) : null}
    </div>
  )
}
