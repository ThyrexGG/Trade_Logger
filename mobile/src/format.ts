/** "+$12.34" / "-$12.34" / "$0.00". */
export function formatMoney(value: number, signed = true): string {
  const abs = Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (!signed || value === 0) return `$${abs}`
  return `${value > 0 ? '+' : '-'}$${abs}`
}

/** Trims float noise off broker prices without forcing a fixed number of decimals. */
export function formatPrice(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return String(Number(value.toPrecision(8)))
}

export function isBuy(direction: string): boolean {
  const d = direction.toUpperCase()
  return d.includes('BUY') || d.includes('LONG')
}

/** "3:42 PM" for today's timestamps, otherwise "Sep 19, 3:42 PM". */
export function formatUpdated(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return '—'
  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  return d.toDateString() === new Date().toDateString()
    ? time
    : `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${time}`
}
