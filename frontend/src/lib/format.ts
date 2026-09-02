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

/** USD amount with sign and 2dp, e.g. "$1,005.67" / "-$42.00". */
export function formatUsd(value: number): string {
  if (!Number.isFinite(value)) return '—'
  const sign = value < 0 ? '-' : ''
  return `${sign}$${Math.abs(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** Percentage with 2dp, e.g. "1.05%". */
export function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return `${value.toFixed(2)}%`
}

/** Lot size at the backend's 0.01 step. */
export function formatLots(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return value.toFixed(2)
}

/** Parses a user-entered number; returns null for blank / non-numeric. */
export function parseNumberInput(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const n = Number(trimmed)
  return Number.isFinite(n) ? n : null
}
