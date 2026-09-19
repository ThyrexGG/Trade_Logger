/** Mirrors api/routers/auth.py response models (kept in sync by hand). */
export interface AuthUser {
  id: string
  email: string
  display_name: string | null
  role: 'owner' | 'member'
}

export interface MeResult {
  mode: 'passphrase' | 'multiuser' | 'supabase'
  authenticated: boolean
  user: AuthUser | null
  error: string | null
  timestamp: string
}

export interface LoginResult {
  ok: boolean
  error: string | null
  expires_at: string | null
  token: string | null
  user: AuthUser | null
  timestamp: string
}
