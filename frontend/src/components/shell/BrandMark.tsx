/**
 * The TradeLogger mark: a trade drawn as a line — a stop below, an entry, and
 * a path that rises to its target — inside a fine square frame. The same
 * vocabulary as the Position Track on Home, so the logo and the product speak
 * one language.
 */
export function BrandMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
      <rect x="0.75" y="0.75" width="26.5" height="26.5" rx="7" fill="var(--tl-surface-elevated)" stroke="var(--tl-border)" strokeWidth="1" />
      <path d="M6.5 19.5h4" stroke="var(--tl-negative)" strokeWidth="1.6" strokeLinecap="round" opacity="0.85" />
      <path d="M7.5 16.5l4.5-3.5 3.5 2.5 6-6.5" fill="none" stroke="var(--tl-accent-fill)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="21.5" cy="9" r="1.9" fill="var(--tl-accent-fill)" />
    </svg>
  )
}

export function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <BrandMark size={compact ? 22 : 26} />
      <span className="text-[14.5px] font-semibold tracking-[-0.015em] text-primary">TradeLogger</span>
    </span>
  )
}
