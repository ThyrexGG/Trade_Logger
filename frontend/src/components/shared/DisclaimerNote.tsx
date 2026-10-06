/**
 * Shared "this is not financial advice" banner for pages that produce a
 * rating, score, or signal-shaped output (Chart Analyzer, Killzone Scanner,
 * Challenge Tracker). Keep the wording identical across pages — it's a
 * standing disclosure, not page-specific copy.
 */
export function DisclaimerNote() {
  return (
    <p className="mb-4 rounded-lg border border-border-subtle bg-surface-elevated/40 p-3 text-[11px] leading-relaxed text-muted">
      Informational only — not financial advice. This tool summarizes data and patterns; it
      doesn't know your risk tolerance, account size, or the rest of the market, and it can be
      wrong. Trading decisions, and their outcomes, are yours alone.
    </p>
  )
}
