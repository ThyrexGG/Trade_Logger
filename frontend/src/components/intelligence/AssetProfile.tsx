import type { AssetProfile as AssetProfileData } from '../../types/intelligence'
import type { LoadState } from '../../lib/useWatchlist'
import { formatPercent } from '../../lib/format'
import {
  DataQualityBadge,
  FreshnessBadge,
  IntelTag,
  ScoreBar,
  SectionCard,
  SkeletonRows,
} from './primitives'

interface AssetProfileProps {
  symbol: string
  state: LoadState
  data: AssetProfileData | null
  error: string | null
  refreshing: boolean
  onRetry: () => void
}

function Overview({ data }: { data: AssetProfileData }) {
  return (
    <SectionCard
      title="Overview"
      action={<FreshnessBadge timestamp={data.timestamp} />}
    >
      <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        <div className="col-span-2 sm:col-span-1">
          <p className="text-[11px] uppercase tracking-wider text-muted">
            Overall edge
          </p>
          <p
            className={`font-mono text-2xl font-semibold tabular-nums ${
              data.overall_edge_score >= 0 ? 'text-positive' : 'text-negative'
            }`}
          >
            {data.overall_edge_score > 0 ? '+' : ''}
            {data.overall_edge_score.toFixed(1)}
          </p>
          <p className="text-[10px] text-muted">scale -100 … +100</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">Context</p>
          <div className="mt-1">
            <IntelTag value={data.context_state} />
          </div>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">
            Factor agreement
          </p>
          <p className="mt-1 font-mono text-sm text-primary">
            {formatPercent(data.factor_agreement_pct)}
          </p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">
            Data quality
          </p>
          <div className="mt-1">
            <DataQualityBadge score={data.data_quality_score} compact />
          </div>
        </div>
      </div>
    </SectionCard>
  )
}

function FactorBreakdown({ data }: { data: AssetProfileData }) {
  const factors = [
    { label: 'Overall edge', score: data.overall_edge_score },
    { label: 'Technical', score: data.technical_score },
    { label: 'Positioning', score: data.positioning_score },
    { label: 'Macro context', score: data.macro_context_score },
  ]
  return (
    <SectionCard title="Factor breakdown">
      <ul className="space-y-3">
        {factors.map((f) => (
          <li key={f.label}>
            <p className="mb-1 text-xs text-secondary">{f.label}</p>
            <ScoreBar score={f.score} />
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-muted">
        Authoritative factor scores from the edge engine, shown on their native
        -100 … +100 scale.
      </p>
    </SectionCard>
  )
}

function Drivers({ data }: { data: AssetProfileData }) {
  return (
    <SectionCard title="Dominant drivers">
      {data.dominant_drivers.length === 0 ? (
        <p className="text-sm text-muted">No dominant drivers returned.</p>
      ) : (
        <ul className="space-y-1.5 text-sm text-primary">
          {data.dominant_drivers.map((d, i) => (
            <li key={i} className="border-l-2 border-l-border pl-3">
              {d}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}

function Conflicts({ data }: { data: AssetProfileData }) {
  return (
    <SectionCard title="Factor conflicts">
      {data.conflicts.length === 0 ? (
        <p className="text-sm text-muted">No factor conflicts detected.</p>
      ) : (
        <ul className="space-y-1.5 text-sm text-warning">
          {data.conflicts.map((c, i) => (
            <li key={i} className="border-l-2 border-l-warning pl-3">
              {c}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}

function Positioning({ data }: { data: AssetProfileData }) {
  const cot = data.cot_sentiment
  if (!cot || Object.keys(cot).length === 0) return null

  return (
    <SectionCard title={cot.factor_name || 'Positioning'}>
      {cot.data_available === false ? (
        <p className="text-sm text-muted">
          {cot.cot_status || 'Positioning data unavailable for this instrument.'}
        </p>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {cot.direction ? <IntelTag value={cot.direction} /> : null}
            {cot.confidence ? (
              <span className="text-[11px] uppercase tracking-wide text-muted">
                {cot.confidence} confidence
              </span>
            ) : null}
            {typeof cot.score === 'number' ? (
              <span className="font-mono text-xs text-secondary">
                score {cot.score > 0 ? '+' : ''}
                {cot.score.toFixed(1)}
              </span>
            ) : null}
          </div>

          {cot.evidence && cot.evidence.length > 0 ? (
            <ul className="space-y-1 text-sm text-secondary">
              {cot.evidence.map((e, i) => (
                <li key={i} className="flex gap-2">
                  {typeof e.points === 'number' ? (
                    <span
                      className={`shrink-0 font-mono text-xs ${
                        e.points >= 0 ? 'text-positive' : 'text-negative'
                      }`}
                    >
                      {e.points > 0 ? '+' : ''}
                      {e.points}
                    </span>
                  ) : null}
                  <span>{e.reason}</span>
                </li>
              ))}
            </ul>
          ) : null}

          {cot.source ? (
            <p className="border-t border-border-subtle pt-2 text-[11px] text-muted">
              {cot.source.provider}
              {cot.source.status ? ` · ${cot.source.status}` : ''}
              {typeof cot.source.age_sec === 'number'
                ? ` · ${Math.round(cot.source.age_sec / 60)}m old`
                : ''}
            </p>
          ) : null}
        </div>
      )}
    </SectionCard>
  )
}

function Surprises({ data }: { data: AssetProfileData }) {
  if (!data.recent_surprises || data.recent_surprises.length === 0) return null
  return (
    <SectionCard title="Recent economic surprises">
      <ul className="space-y-1.5 text-sm text-secondary">
        {data.recent_surprises.map((s, i) => (
          <li key={i}>
            {Object.entries(s)
              .map(([k, v]) => `${k}: ${String(v)}`)
              .join(' · ')}
          </li>
        ))}
      </ul>
    </SectionCard>
  )
}

/** Deep contextual profile for one asset — display only, no calculation. */
export function AssetProfile({
  symbol,
  state,
  data,
  error,
  refreshing,
  onRetry,
}: AssetProfileProps) {
  if (state === 'loading' && !data) {
    return (
      <div className="space-y-4">
        <SectionCard title="Overview">
          <SkeletonRows rows={3} />
        </SectionCard>
        <SectionCard title="Factor breakdown">
          <SkeletonRows rows={4} />
        </SectionCard>
      </div>
    )
  }

  if (state === 'error' && !data) {
    return (
      <SectionCard title="Asset profile">
        <p className="text-sm text-negative">Profile unavailable for {symbol}</p>
        <p className="mt-1 text-xs text-muted">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
        >
          Retry
        </button>
      </SectionCard>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-4">
      {state === 'error' && error ? (
        <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
          Showing last profile — refresh failed: {error}
        </p>
      ) : refreshing ? (
        <p className="text-[11px] text-muted">Refreshing…</p>
      ) : null}

      <Overview data={data} />
      <div className="grid gap-4 lg:grid-cols-2">
        <FactorBreakdown data={data} />
        <Positioning data={data} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Drivers data={data} />
        <Conflicts data={data} />
      </div>
      <Surprises data={data} />
    </div>
  )
}
