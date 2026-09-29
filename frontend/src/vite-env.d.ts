/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL prepended to API paths. Empty in dev (Vite proxy handles /api/*). */
  readonly VITE_API_BASE_URL?: string
  /** Dev-only: override the FastAPI proxy target used by vite.config.ts. */
  readonly VITE_DEV_API_PROXY_TARGET?: string
  /** 'multiuser' enables invite-only email+password auth (W10); anything else = the single-user passphrase gate. */
  readonly VITE_AUTH_MODE?: string
  /** 'friends' hides the research/execution-review pages from the sidebar and routes (see lib/navigation.ts); anything else = the full app. */
  readonly VITE_APP_TIER?: string
  /** 'local-fallback' marks a build made specifically for run_local_fallback.py (see .env.production.local and lib/appMode.ts) — shows the "Local mode" indicator in the TopBar. The real Cloudflare build never sets this. */
  readonly VITE_APP_MODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
