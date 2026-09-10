/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL prepended to API paths. Empty in dev (Vite proxy handles /api/*). */
  readonly VITE_API_BASE_URL?: string
  /** Dev-only: override the FastAPI proxy target used by vite.config.ts. */
  readonly VITE_DEV_API_PROXY_TARGET?: string
  /** 'multiuser' enables invite-only email+password auth (W10); anything else = the single-user passphrase gate. */
  readonly VITE_AUTH_MODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
