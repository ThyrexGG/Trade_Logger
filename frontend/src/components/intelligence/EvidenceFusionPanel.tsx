import { useState } from 'react'
import type {
  AssetIntelligence,
  EvidenceCategory,
  EvidenceStateValue,
} from '../../types/intelligence'
import type { LoadState } from '../../lib/useWatchlist'
import { timeAgo } from '../../lib/format'
import {
  IntelTag,
  ScoreBar,
  SectionCard,
  SectionError,
  SkeletonRows,
  toneForIntel,
  type IntelTone,
} from './primitives'

/**
 * Unified Evidence Fusion panel (Phase 67). Consumes the single canonical
 * GET /api/intelligence/asset/{asset} snapshot. Answers, in ~3 seconds:
 *   1. What is the current evidence state?     -> header + coverage
 *   2. Which categories agree / conflict?      -> cross-category banner + cards
 *   3. What evidence is missing?               -> coverage + data gaps
 *   4. How fresh is the evidence?              -> per-card freshness
 *   5. Where did it come from?                 -> expandable provenance
 * Read-only. Category scores are context, never an execution signal.
 */

const STATE_TONE: Record<EvidenceStateValue, IntelTone> = {
  AVAILABLE: 'neutral',
  INSUFFICIENT_EVIDENCE: 'warning',
  PROVIDER_UNAVAILABLE: 'negative',
  STALE: 'warning',
  CONFLICT: 'negative',
  NOT_APPLICABLE: 'neutral',
}

const STATE_LABEL: Record<EvidenceStateValue, string> = {
  AVAILABLE: 'Available',
  INSUFFICIENT_EVIDENCE: 'Insufficient evidence',
  PROVIDER_UNAVAILABLE: 'Provider unavailable',
  STALE: 'Stale',
  CONFLICT: 'Conflict',
  NOT_APPLICABLE: 'N/A',
}

function fmtScore(v: number | null): string {
  if (v === null || Number.isNaN(v)) return '—'
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}`
}

/**
 * Provenance badge — a deterministic prior must never look like real market
 * evidence (Phase 68). Real candle-derived / released data is neutral-toned;
 * a model prior is warning-toned and explicitly labelled.
 */
const PROVENANCE_LABEL: Record<string, { text: string; tone: IntelTone }> = {
  historical_ohlcv: { text: 'historical candles', tone: 'neutral' },
  live_ohlcv: { text: 'live candles', tone: 'positive' },
  live: { text: 'live provider', tone: 'neutral' },
  seed_demo: { text: 'seed / demo data', tone: 'warning' },
  derived: { text: 'derived', tone: 'neutral' },
  deterministic_prior: { text: 'model prior — not market data', tone: 'warning' },
}

function ProvenanceBadge({ provenance }: { provenance: string | null }) {
  if (!provenance) return null
  const meta = PROVENANCE_LABEL[provenance] ?? { text: provenance, tone: 'neutral' as IntelTone }
  return <IntelTag value={meta.text} tone={meta.tone} />
}

function CrossCategoryBanner({ snap }: { snap: AssetIntelligence }) {
  const s = snap.cross_category_state
  const tone: IntelTone =
    s === 'CONFLICT'
      ? 'negative'
      : s === 'AGREEMENT'
        ? 'positive'
        : s === 'MIXED'
          ? 'warning'
          : 'neutral'
  const cc = snap.cross_category
  return (
    <div
      className={`rounded-md border px-3 py-2 text-xs ${
        {
          positive: 'border-positive/30 bg-positive/10 text-positive',
          negative: 'border-negative/30 bg-negative/10 text-negative',
          warning: 'border-warning/30 bg-warning/10 text-warning',
          neutral: 'border-border-subtle bg-surface-elevated text-secondary',
        }[tone]
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="font-semibold uppercase tracking-wide">
          Cross-category: {s.replace('_', ' ')}
        </span>
        {cc.agreement_ratio !== null ? (
          <span className="text-muted">
            agreement {(cc.agreement_ratio * 100).toFixed(0)}%
          </span>
        ) : null}
      </div>
      {cc.note ? <p className="mt-1 text-muted">{cc.note}</p> : null}
      {cc.conflicting_categories.length > 0 ? (
        <p className="mt-1 text-muted">
          Minority side: {cc.conflicting_categories.join(', ')}
        </p>
      ) : null}
    </div>
  )
}

function Coverage({ snap }: { snap: AssetIntelligence }) {
  const c = snap.coverage
  const pct = c.coverage_ratio !== null ? Math.round(c.coverage_ratio * 100) : null
  return (
    <div className="rounded-md border border-border-subtle bg-surface-elevated px-3 py-2">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-semibold uppercase tracking-wide text-secondary">
          Evidence coverage
        </span>
        <span className="font-mono tabular-nums text-primary">
          {c.available_categories}/{c.total_categories}
          {pct !== null ? ` · ${pct}%` : ''}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {Object.entries(c.per_category).map(([cat, st]) => (
          <IntelTag
            key={cat}
            value={cat}
            label={undefined}
            tone={STATE_TONE[st as EvidenceStateValue] ?? 'neutral'}
            className={st === 'AVAILABLE' ? 'opacity-90' : ''}
          />
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted">
        {c.provider_unavailable_categories} provider-unavailable ·{' '}
        {c.insufficient_categories} insufficient. A provider outage is not
        &ldquo;insufficient evidence&rdquo;, and neither is neutral.
      </p>
    </div>
  )
}

function CategoryCard({ cat }: { cat: EvidenceCategory }) {
  const [open, setOpen] = useState(false)
  const tone = STATE_TONE[cat.state] ?? 'neutral'
  const populated = cat.state === 'AVAILABLE' || cat.state === 'CONFLICT'
  const age = cat.evidence[0]?.release_timestamp ?? cat.evidence[0]?.available_timestamp
  return (
    <div className="rounded-md border border-border-subtle bg-surface">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-secondary">
            {cat.category}
          </span>
          <IntelTag value={STATE_LABEL[cat.state] ?? cat.state} tone={tone} />
          {populated && cat.direction !== 'UNKNOWN' ? (
            <IntelTag value={cat.direction} tone={toneForIntel(cat.direction)} />
          ) : null}
          <ProvenanceBadge provenance={cat.provenance} />
        </span>
        <span className="flex items-center gap-2 font-mono text-xs tabular-nums text-muted">
          {cat.score !== null ? fmtScore(cat.score) : ''}
          {cat.freshness ? <span>· {cat.freshness}</span> : null}
          <span aria-hidden>{open ? '▾' : '▸'}</span>
        </span>
      </button>

      {populated && cat.score !== null ? (
        <div className="px-3 pb-2">
          <ScoreBar score={cat.score} size="sm" />
        </div>
      ) : null}

      {!populated && cat.reason ? (
        <p className="px-3 pb-2 text-[11px] text-muted">
          {cat.reason}
          {cat.next_dependency ? (
            <span className="block text-stale">Needs: {cat.next_dependency}</span>
          ) : null}
        </p>
      ) : null}

      {open ? (
        <div className="border-t border-border-subtle px-3 py-2">
          {cat.sources.length > 0 ? (
            <p className="mb-2 text-[11px] text-muted">
              Sources: {cat.sources.join(', ')}
              {cat.provenance ? ` · ${cat.provenance}` : ''}
              {age ? ` · released ${timeAgo(age) ?? age}` : ''}
            </p>
          ) : null}
          {cat.evidence[0]?.calculation_window ? (
            <p className="mb-2 text-[11px] text-muted">
              Window: {cat.evidence[0].calculation_window}
              {cat.evidence[0].latest_input_timestamp
                ? ` · latest input ${cat.evidence[0].latest_input_timestamp.slice(0, 16).replace('T', ' ')}Z`
                : ''}
            </p>
          ) : null}
          {cat.evidence.length > 0 ? (
            <ul className="space-y-1">
              {cat.evidence.slice(0, 8).map((e, i) => (
                <li key={i} className="flex items-baseline justify-between gap-2 text-[11px]">
                  <span className="text-secondary">
                    {e.metric}
                    {e.provenance === 'deterministic_prior' ? (
                      <span className="ml-1 text-warning">(model prior)</span>
                    ) : null}
                  </span>
                  <span className="shrink-0 font-mono tabular-nums text-muted">
                    {e.value !== null ? e.value : ''}
                    {e.unit ? ` ${e.unit}` : ''}
                    {e.timeframe ? ` · ${e.timeframe}` : e.source ? ` · ${e.source}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[11px] text-muted">No evidence items.</p>
          )}
        </div>
      ) : null}
    </div>
  )
}

function DataGaps({ snap }: { snap: AssetIntelligence }) {
  if (snap.data_gaps.length === 0) return null
  return (
    <div className="rounded-md border border-border-subtle bg-surface-elevated px-3 py-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-secondary">
        Data gaps
      </p>
      <ul className="mt-1 space-y-1">
        {snap.data_gaps.map((g, i) => (
          <li key={i} className="text-[11px] text-muted">
            <span className="font-mono text-stale">{String(g.category ?? g.state ?? '')}</span>{' '}
            {String(g.reason ?? '')}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function EvidenceFusionPanel({
  symbol,
  state,
  data,
  error,
  refreshing,
  onRetry,
}: {
  symbol: string
  state: LoadState
  data: AssetIntelligence | null
  error: string | null
  refreshing: boolean
  onRetry: () => void
}) {
  return (
    <SectionCard
      title="Unified Evidence"
      action={
        <span className="flex items-center gap-2 text-[11px] text-muted">
          {data ? (
            <>
              <span className="rounded bg-surface-elevated px-1 uppercase">{data.mode}</span>
              <span>as of {timeAgo(data.as_of) ?? data.as_of}</span>
            </>
          ) : null}
          {refreshing ? <span>· refreshing</span> : null}
        </span>
      }
    >
      {state === 'loading' ? (
        <SkeletonRows rows={6} />
      ) : state === 'error' || !data ? (
        <SectionError message={error} onRetry={onRetry} />
      ) : (
        <div className="space-y-3">
          <p className="text-[11px] text-muted">
            One timestamp-correct evidence view for {symbol}. Category scores are
            contextual intelligence — never an execution signal.
          </p>
          <CrossCategoryBanner snap={data} />
          <Coverage snap={data} />
          <div className="space-y-2">
            {data.categories.map((c) => (
              <CategoryCard key={c.category} cat={c} />
            ))}
          </div>
          <DataGaps snap={data} />
          {data.provider_health?.provider_state ? (
            <p className="text-[11px] text-muted">
              Macro provider state:{' '}
              <span className="font-mono">
                {String(data.provider_health.provider_state)}
              </span>{' '}
              · model {data.model_version}
            </p>
          ) : null}
        </div>
      )}
    </SectionCard>
  )
}
