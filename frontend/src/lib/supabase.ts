/**
 * Auth mode selector.
 *
 * `VITE_AUTH_MODE=multiuser` turns on the invite-only email + password sign-in
 * (platform plan W10 — the backend owns identity, sessions live in a cookie).
 * Anything else runs the single-user passphrase gate exactly as before.
 *
 * (The file keeps its old name so imports elsewhere don't churn. There is no
 * Supabase client any more — identity is entirely first-party.)
 */
export const AUTH_MODE: 'passphrase' | 'multiuser' =
  import.meta.env.VITE_AUTH_MODE === 'multiuser' ? 'multiuser' : 'passphrase'
