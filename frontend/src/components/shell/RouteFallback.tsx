/**
 * Suspense fallback shown while a lazily-loaded route chunk downloads.
 * Deliberately minimal — the persistent shell (sidebar + top bar) stays
 * mounted around it, so navigation still feels immediate.
 */
export function RouteFallback() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex h-full min-h-[40vh] w-full items-center justify-center p-8 text-sm text-muted"
    >
      <span className="inline-flex items-center gap-2">
        <span className="h-2 w-2 animate-pulse rounded-full bg-muted" />
        Loading view…
      </span>
    </div>
  )
}
