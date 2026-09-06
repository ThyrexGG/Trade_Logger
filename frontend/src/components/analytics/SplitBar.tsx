/**
 * Two-sided proportion bar — the legacy analytics page's "Average Win vs Loss"
 * and "Long / Short Counts" visual. `left` / `right` are non-negative
 * magnitudes; the bar shows their share and the labels underneath.
 */
export function SplitBar({
  leftLabel,
  rightLabel,
  left,
  right,
  leftValue,
  rightValue,
}: {
  leftLabel: string
  rightLabel: string
  left: number
  right: number
  leftValue: string
  rightValue: string
}) {
  const total = left + right
  const leftPct = total > 0 ? (left / total) * 100 : 50
  const rightPct = 100 - leftPct

  return (
    <div>
      <div className="flex items-baseline justify-between text-[11px]">
        <span className="font-mono text-positive">
          {leftLabel} {leftValue}
        </span>
        <span className="font-mono text-muted tabular-nums">
          {leftPct.toFixed(1)}% / {rightPct.toFixed(1)}%
        </span>
        <span className="font-mono text-negative">
          {rightLabel} {rightValue}
        </span>
      </div>
      <div className="mt-1 flex h-2.5 overflow-hidden rounded bg-surface-elevated/40">
        <div className="bg-positive/60" style={{ width: `${leftPct}%` }} />
        <div className="bg-negative/60" style={{ width: `${rightPct}%` }} />
      </div>
    </div>
  )
}
