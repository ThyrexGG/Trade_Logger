import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { getAuthStatus, login as apiLogin, logout as apiLogout } from '../api/auth'
import { setUnauthorizedHandler } from '../api/client'

type AuthState = 'loading' | 'open' | 'authed' | 'locked'

interface AuthContextValue {
  /** loading = still checking; open = no auth configured; authed = logged in; locked = login required */
  state: AuthState
  login: (password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Gates the whole app. On mount it asks `/api/auth/status`:
 *  - auth not configured on the server  -> `open`, render the app
 *  - configured + valid session         -> `authed`, render the app
 *  - configured + no session            -> `locked`, render <LoginScreen>
 * Any 401 from a normal API call flips the app back to `locked`.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>('loading')

  const refresh = useCallback((signal?: AbortSignal) => {
    return getAuthStatus(signal)
      .then((s) => {
        if (signal?.aborted) return
        setState(!s.auth_required ? 'open' : s.authenticated ? 'authed' : 'locked')
      })
      .catch(() => {
        if (signal?.aborted) return
        // status endpoint is unauthenticated — a failure here is a network/server
        // problem, not a lockout. Let the app render and surface its own errors.
        setState('open')
      })
  }, [])

  useEffect(() => {
    const c = new AbortController()
    refresh(c.signal)
    return () => c.abort()
  }, [refresh])

  useEffect(() => {
    setUnauthorizedHandler(() => setState('locked'))
    return () => setUnauthorizedHandler(null)
  }, [])

  const login = useCallback(async (password: string) => {
    await apiLogin(password) // throws ApiError on 401/429 — caller shows the message
    await refresh()
  }, [refresh])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setState('locked')
    }
  }, [])

  return (
    <AuthContext.Provider value={{ state, login, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
