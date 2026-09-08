import { createClient, type SupabaseClient } from '@supabase/supabase-js'

/**
 * Supabase Auth is the identity provider for the multi-user build (platform
 * plan W8). It is enabled only when the build sets `VITE_AUTH_MODE=supabase`
 * *and* both connection values are present — otherwise the app runs the
 * single-user passphrase gate exactly as before.
 *
 * `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` are public (the anon key is
 * safe in the client bundle — row access is still gated by the backend and,
 * later, RLS). Never put the service-role key or the JWT secret here.
 */
const url = (import.meta.env.VITE_SUPABASE_URL ?? '').trim()
const anonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY ?? '').trim()

export const AUTH_MODE: 'supabase' | 'passphrase' =
  import.meta.env.VITE_AUTH_MODE === 'supabase' && url && anonKey ? 'supabase' : 'passphrase'

export const supabase: SupabaseClient | null =
  AUTH_MODE === 'supabase'
    ? createClient(url, anonKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
        },
      })
    : null

/** Current access token, or null. The client library keeps it auto-refreshed. */
export async function currentAccessToken(): Promise<string | null> {
  if (!supabase) return null
  try {
    const { data } = await supabase.auth.getSession()
    return data.session?.access_token ?? null
  } catch {
    return null
  }
}
