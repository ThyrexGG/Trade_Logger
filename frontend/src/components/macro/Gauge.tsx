/**
 * Compact semicircular macro-bias gauge (Phase 64). Pure inline SVG — no chart
 * library. Maps an integer score in [-10, 10] to a needle angle; the arc is
 * tinted red (bearish) → muted (neutral) → positive (bullish). `null` score
 * renders a dimmed, needle-less gauge (INSUFFICIENT_EVIDENCE).
 */
export function Gauge({
  score,
  size = 96,
  label,
}: {
  score: number | null | undefined
  size?: number
  label?: string
}) {
  const w = size
  const h = size * 0.62
  const cx = w / 2
  const cy = h - 4
  const r = w / 2 - 8
  const clamped = score == null ? null : Math.max(-10, Math.min(10, score))
  // -10 -> 180deg (left), +10 -> 0deg (right)
  const angle = clamped == null ? 90 : 180 - ((clamped + 10) / 20) * 180
  const rad = (angle * Math.PI) / 180
  const nx = cx + Math.cos(rad) * (r - 6)
  const ny = cy - Math.sin(rad) * (r - 6)

  const arc = (a0: number, a1: number) => {
    const p0 = [cx + Math.cos((a0 * Math.PI) / 180) * r, cy - Math.sin((a0 * Math.PI) / 180) * r]
    const p1 = [cx + Math.cos((a1 * Math.PI) / 180) * r, cy - Math.sin((a1 * Math.PI) / 180) * r]
    return `M ${p0[0].toFixed(1)} ${p0[1].toFixed(1)} A ${r} ${r} 0 0 1 ${p1[0].toFixed(1)} ${p1[1].toFixed(1)}`
  }

  const tone =
    clamped == null ? 'text-muted' : clamped >= 2 ? 'text-positive' : clamped <= -2 ? 'text-negative' : 'text-secondary'

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        width={w}
        height={h}
        role="img"
        aria-label={`Macro gauge ${clamped == null ? 'insufficient evidence' : clamped}`}
      >
        <path d={arc(180, 120)} stroke="var(--tl-negative)" strokeWidth="6" fill="none" opacity={clamped == null ? 0.25 : 0.75} strokeLinecap="round" />
        <path d={arc(120, 60)} stroke="var(--tl-text-muted)" strokeWidth="6" fill="none" opacity={clamped == null ? 0.25 : 0.6} />
        <path d={arc(60, 0)} stroke="var(--tl-positive)" strokeWidth="6" fill="none" opacity={clamped == null ? 0.25 : 0.75} strokeLinecap="round" />
        {clamped != null ? (
          <>
            <line x1={cx} y1={cy} x2={nx.toFixed(1)} y2={ny.toFixed(1)} stroke="var(--tl-text-primary)" strokeWidth="2" strokeLinecap="round" />
            <circle cx={cx} cy={cy} r="3" fill="var(--tl-text-primary)" />
          </>
        ) : null}
      </svg>
      <div className={`-mt-1 font-mono text-lg font-semibold tabular-nums ${tone}`}>
        {clamped == null ? '—' : `${clamped > 0 ? '+' : ''}${clamped}`}
      </div>
      {label ? <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div> : null}
    </div>
  )
}
