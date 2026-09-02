/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL prepended to API paths. Empty in dev (Vite proxy handles /api/*). */
  readonly VITE_API_BASE_URL?: string
  /** Dev-only: override the FastAPI proxy target used by vite.config.ts. */
  readonly VITE_DEV_API_PROXY_TARGET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
