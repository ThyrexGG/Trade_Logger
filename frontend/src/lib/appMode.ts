/** True only in a build made specifically to serve the local fallback
 *  (run_local_fallback.py) — baked in via frontend/.env.production.local,
 *  a file the real Cloudflare Pages build never sees. Lets the UI show an
 *  unmissable "local mode" indicator instead of the user having to guess
 *  which copy of their data — this PC's own, or the synced cloud one — they're
 *  actually looking at. */
export function isLocalFallbackBuild(): boolean {
  return import.meta.env.VITE_APP_MODE === 'local-fallback'
}
