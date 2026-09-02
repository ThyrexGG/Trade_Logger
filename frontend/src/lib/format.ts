/** Price precision scaled to magnitude — FX pairs need more decimals than indices. */
export function formatPrice(value: number): string {
  if (!Number.isFinite(value)) return '—'
  const abs = Math.abs(value)
  let decimals: number
  if (abs === 0) decimals = 2
  else if (abs < 10) decimals = 5
  else if (abs < 1000) decimals = 3
  else decimals = 2
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/** Spread shown at a fixed, generous precision (values are small). */
export function formatSpread(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 5,
  })
}

export function formatScore(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return (value > 0 ? '+' : '') + value.toFixed(0)
}

/** Compact "x s / m ago" from an ISO timestamp; null when unparseable. */
export function timeAgo(iso: string | undefined, now: number = Date.now()): string | null {
  if (!iso) return null
  const then = Date.parse(iso)
  if (Number.isNaN(then)) return null
  const seconds = Math.max(0, Math.round((now - then) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  return `${hours}h ago`
}

export function ageSeconds(iso: string | undefined, now: number = Date.now()): number | null {
  if (!iso) return null
  const then = Date.parse(iso)
  if (Number.isNaN(then)) return null
  return Math.max(0, (now - then) / 1000)
}
