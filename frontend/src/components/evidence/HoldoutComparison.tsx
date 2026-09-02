import type { ForwardEvidenceState } from '../../types/evidence'
import { numField } from '../../types/evidence'
import { Delta, EvidenceStatusTag, SectionCard, evidenceTone } from './primitives'

interface RowSpec {
  label: string
  histKey: string
  fwdKey: string
  deltaKey: string
  unit?: string
  precision?: number
  deltaGoodPositive?: boolean
}

const ROWS: RowSpec[] = [
  { label: 'Sample N', histKey: 'trades_n', fwdKey: 'trades_n', deltaKey: '', precision: 0 },
  { label: 'Expectancy E[R]', histKey: 'expectancy_r', fwdKey: 'expectancy_r', deltaKey: 'expectancy_delta', unit: ' R', precision: 3 },
  { label: 'Win rate', histKey: 'win_rate_pct', fwdKey: 'win_rate_pct', deltaKey: 'win_rate_delta_pct', unit: '%', precision: 1 },
  { label: 'Profit factor', histKey: 'profit_factor', fwdKey: 'profit_factor', deltaKey: 'profit_factor_delta', precision: 2 },
  { label: 'Max drawdown R', histKey: 'max_drawdown_r', fwdKey: 'max_drawdown_r', deltaKey: 'drawdown_divergence_r', unit: ' R', precision: 2, deltaGoodPositive: false },
]

function cell(v: number | null, unit = '', precision = 2): string {
  if (v === null || !Number.isFinite(v)) return '—'
  return `${v.toFixed(precision)}${unit}`
}

/**
 * Side-by-side historical-holdout vs forward comparison. Historical and forward
 * columns come straight from `holdout.historical` / `holdout.forward`; the Δ
 * column is ONLY the backend's `holdout.deltas` — never derived here. A missing
 * delta renders "Not exposed", not a computed value.
 */
export function HoldoutComparison({ data }: { data: ForwardEvidenceState }) {
  const hist = data.holdout.historical
  const fwd = data.holdout.forward
  const deltas = data.holdout.deltas as Record<string, unknown>
  const hasForward = data.metrics.trades_n > 0

  return (
    <SectionCard
      title="Historical holdout vs forward"
      action={
        <EvidenceStatusTag
          value={data.holdout.comparison_verdict}
          tone={evidenceTone(data.holdout.comparison_verdict)}
          size="sm"
        />
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead className="border-b border-border text-muted">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium">Metric</th>
              <th className="px-2 py-1.5 text-right font-medium">
                Historical holdout
              </th>
              <th className="px-2 py-1.5 text-right font-medium">Forward</th>
              <th className="px-2 py-1.5 text-right font-medium">
                Backend Δ
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => {
              const hv = numField(hist, r.histKey)
              const fv = hasForward ? numField(fwd, r.fwdKey) : null
              const dv = r.deltaKey ? numField(deltas, r.deltaKey) : undefined
              return (
                <tr key={r.label} className="border-b border-border-subtle/60">
                  <td className="px-2 py-1.5 text-secondary">{r.label}</td>
                  <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">
                    {cell(hv, r.unit, r.precision)}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">
                    {hasForward ? cell(fv, r.unit, r.precision) : '—'}
                  </td>
                  <td className="px-2 py-1.5 text-right">
                    {!r.deltaKey ? (
                      <span className="text-muted">n/a</span>
                    ) : !hasForward ? (
                      <span className="text-muted">—</span>
                    ) : dv === null ? (
                      <span className="text-muted">Not exposed</span>
                    ) : (
                      <Delta
                        value={dv}
                        unit={r.unit === '%' ? ' pp' : r.unit}
                        precision={r.precision}
                        goodWhenPositive={r.deltaGoodPositive ?? true}
                      />
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {data.holdout.explanation ? (
        <p className="mt-3 text-[11px] text-muted">{data.holdout.explanation}</p>
      ) : null}
      <p className="mt-1 text-[11px] text-muted">
        Datasets are compared, never pooled — {data.holdout.pooling_prevention_check}.
      </p>
    </SectionCard>
  )
}
