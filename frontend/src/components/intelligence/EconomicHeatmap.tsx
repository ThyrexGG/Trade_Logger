import { useId, useMemo, useState, type ReactNode } from 'react'
import type {
  EconomicHeatmapResponse,
  HeatmapCategory,
  HeatmapIndicator,
} from '../../types/intelligence'
import { HEATMAP_CATEGORIES } from '../../types/intelligence'
import type { Section } from '../../lib/useIntelligence'
import { formatMacroValue } from '../../lib/format'
import { FreshnessBadge, SectionCard, SectionError, SkeletonRows } from './primitives'

const CATEGORY_LABEL: Record<HeatmapCategory, string> = {
  growth: 'Growth',
  inflation: 'Inflation',
  labor: 'Labor',
  rates: 'Rates',
  surprise: 'Surprise',
}

function isHex(s: string | undefined): s is string {
  return !!s && /^#[0-9a-fA-F]{6}$/.test(s)
}

function Cell({ ind }: { ind: HeatmapIndicator | undefined }) {
  if (!ind || (ind.actual === undefined && ind.directional_interpretation === undefined)) {
    return <td className="px-2 py-1.5 text-center text-muted">—</td>
  }
  const tint = isHex(ind.tint_color) ? ind.tint_color : undefined
  const tooltip = [
    ind.display_name,
    ind.actual !== null && ind.actual !== undefined
      ? `Actual ${formatMacroValue(ind.actual)}  Forecast ${formatMacroValue(ind.forecast)}  Prev ${formatMacroValue(ind.previous)}`
      : null,
    ind.z_score !== null && ind.z_score !== undefined
      ? `Surprise z-score ${ind.z_score.toFixed(2)}`
      : null,
    ind.source ? `Source: ${ind.source}` : null,
    ind.release_timestamp ? `Released: ${new Date(ind.release_timestamp).toLocaleDateString()}` : null,
  ]
    .filter(Boolean)
    .join('\n')

  return (
    <td
      className="px-2 py-1.5"
      style={tint ? { backgroundColor: `${tint}1a` } : undefined}
      title={tooltip || undefined}
    >
      <div className="flex flex-col gap-0.5">
        <span className="flex items-center gap-1 text-[11px] font-medium text-primary">
          {tint ? (
            <span
              className="inline-block h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: tint }}
              aria-hidden="true"
            />
          ) : null}
          {ind.directional_interpretation ?? '—'}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-secondary">
          {formatMacroValue(ind.actual)}
          {ind.forecast !== null && ind.forecast !== undefined ? (
            <span className="text-muted"> vs {formatMacroValue(ind.forecast)}</span>
          ) : null}
        </span>
      </div>
    </td>
  )
}

export function EconomicHeatmap({
  section,
  onRetry,
}: {
  section: Section<EconomicHeatmapResponse>
  onRetry: () => void
}) {
  const searchId = useId()
  const [query, setQuery] = useState('')
  const data = section.data

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (data?.matrix ?? []).filter(
      (r) =>
        !q ||
        r.economy_code.toLowerCase().includes(q) ||
        r.country_name.toLowerCase().includes(q),
    )
  }, [data, query])

  let body: ReactNode
  if (section.state === 'loading' && !data) {
    body = <SkeletonRows rows={6} />
  } else if (section.state === 'error' && !data) {
    body = <SectionError message={section.error} onRetry={onRetry} />
  } else if (!data || data.matrix.length === 0) {
    body = <p className="text-sm text-muted">No economic heatmap data returned.</p>
  } else {
    body = (
      <>
        <div className="flex items-center gap-2">
          <label htmlFor={searchId} className="sr-only">
            Filter economies
          </label>
          <input
            id={searchId}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter economy…"
            autoComplete="off"
            className="w-40 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:outline-none focus:border-accent"
          />
          <span className="ml-auto text-[11px] tabular-nums text-muted">
            {rows.length}/{data.matrix.length} economies
          </span>
        </div>

        {rows.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No economies match the filter.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-collapse text-xs">
              <thead className="border-b border-border-subtle text-muted">
                <tr>
                  <th className="sticky left-0 bg-surface px-2 py-1.5 text-left font-medium">
                    Economy
                  </th>
                  {HEATMAP_CATEGORIES.map((c) => (
                    <th key={c} className="px-2 py-1.5 text-left font-medium">
                      {CATEGORY_LABEL[c]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.economy_code} className="border-b border-border-subtle/60">
                    <th className="sticky left-0 bg-surface px-2 py-1.5 text-left font-mono font-semibold text-primary">
                      <span className="mr-1" aria-hidden="true">{r.flag}</span>
                      {r.economy_code}
                      <span className="ml-1 font-sans text-[10px] font-normal text-muted">
                        {r.country_name}
                      </span>
                    </th>
                    {HEATMAP_CATEGORIES.map((c) => (
                      <Cell key={c} ind={r[c]} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-3 text-[11px] text-muted">
          Values are authoritative macro releases (actual vs forecast). Cell tint
          is the backend's own classification colour.
        </p>
      </>
    )
  }

  return (
    <SectionCard
      title="Economic heatmap"
      action={data ? <FreshnessBadge timestamp={data.timestamp} /> : null}
    >
      {body}
    </SectionCard>
  )
}
