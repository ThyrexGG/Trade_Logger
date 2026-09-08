/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL prepended to API paths. Empty in dev (Vite proxy handles /api/*). */
  readonly VITE_API_BASE_URL?: string
  /** Dev-only: override the FastAPI proxy target used by vite.config.ts. */
  readonly VITE_DEV_API_PROXY_TARGET?: string
  /** 'supabase' enables multi-user auth (W8); anything else = the single-user passphrase gate. */
  readonly VITE_AUTH_MODE?: string
  /** Supabase project URL — required when VITE_AUTH_MODE=supabase. Public. */
  readonly VITE_SUPABASE_URL?: string
  /** Supabase anon (publishable) key — required when VITE_AUTH_MODE=supabase. Public. */
  readonly VITE_SUPABASE_ANON_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
