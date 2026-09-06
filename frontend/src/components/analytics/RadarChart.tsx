interface Axis {
  label: string
  /** 0–100 */
  value: number
}

/**
 * Small dependency-free SVG radar/spider chart. Axes are 0–100 index scores;
 * the legacy Streamlit analytics page drew the same five-axis shape.
 */
export function RadarChart({ axes, size = 240 }: { axes: Axis[]; size?: number }) {
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 34
  const n = axes.length
  const rings = [0.25, 0.5, 0.75, 1]

  const pointAt = (i: number, frac: number) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2
    return [cx + Math.cos(angle) * r * frac, cy + Math.sin(angle) * r * frac] as const
  }

  const shape = axes
    .map((a, i) => pointAt(i, Math.max(0, Math.min(1, a.value / 100)))
      .join(','))
    .join(' ')

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto block h-auto w-full max-w-[280px]">
      {rings.map((f) => (
        <polygon
          key={f}
          points={axes.map((_, i) => pointAt(i, f).join(',')).join(' ')}
          fill="none"
          stroke="currentColor"
          className="text-border-subtle"
          strokeWidth={1}
        />
      ))}
      {axes.map((_, i) => {
        const [x, y] = pointAt(i, 1)
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={x}
            y2={y}
            stroke="currentColor"
            className="text-border-subtle"
            strokeWidth={1}
          />
        )
      })}
      <polygon
        points={shape}
        className="fill-accent/25 stroke-accent"
        strokeWidth={1.5}
      />
      {axes.map((a, i) => {
        const [x, y] = pointAt(i, 1.16)
        return (
          <text
            key={a.label}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-muted text-[9px]"
          >
            {a.label}
          </text>
        )
      })}
    </svg>
  )
}
