import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { getAuthStatus, getMe, login as apiLogin, logout as apiLogout, type AuthUser } from '../api/auth'
import { setAuthTokenProvider, setUnauthorizedHandler } from '../api/client'
import { AUTH_MODE, currentAccessToken, supabase } from './supabase'

/**
 * loading = still checking · open = no auth configured · authed = logged in ·
 * locked = sign-in required · pending = signed in with Supabase but this email
 * is not invited yet (or access could not be verified).
 */
type AuthState = 'loading' | 'open' | 'authed' | 'locked' | 'pending'

interface AuthContextValue {
  state: AuthState
  mode: 'passphrase' | 'supabase'
  user: AuthUser | null
  /** Set when state === 'pending' — why access is not granted. */
  accessMessage: string | null
  /** passphrase mode */
  loginPassphrase: (password: string) => Promise<void>
  /** supabase mode */
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>
  /** supabase mode — re-check access (used by the "pending" retry button) */
  recheck: () => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

const notInThisMode = (what: string) => () => {
  throw new Error(`${what} is not available in ${AUTH_MODE} auth mode`)
}

// ---------------------------------------------------------------------------
// Passphrase mode (W3, single user) — unchanged behaviour.
// ---------------------------------------------------------------------------

function PassphraseAuthProvider({ children }: { children: ReactNode }) {
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

  const loginPassphrase = useCallback(
    async (password: string) => {
      await apiLogin(password) // throws ApiError on 401/429 — caller shows the message
      await refresh()
    },
    [refresh],
  )

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setState('locked')
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        state,
        mode: 'passphrase',
        user: null,
        accessMessage: null,
        loginPassphrase,
        signIn: notInThisMode('Email sign-in'),
        signUp: notInThisMode('Sign-up'),
        recheck: () => {},
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Supabase mode (W8, multi-user).
// ---------------------------------------------------------------------------

function SupabaseAuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [accessMessage, setAccessMessage] = useState<string | null>(null)
  const evaluating = useRef(false)

  const evaluate = useCallback(async () => {
    if (!supabase || evaluating.current) return
    evaluating.current = true
    try {
      const token = await currentAccessToken()
      if (!token) {
        setUser(null)
        setAccessMessage(null)
        setState('locked')
        return
      }
      try {
        const me = await getMe()
        if (me.authenticated && me.user) {
          setUser(me.user)
          setAccessMessage(null)
          setState('authed')
        } else {
          setUser(null)
          setAccessMessage(me.error ?? 'Access has not been granted for this account.')
          setState('pending')
        }
      } catch {
        // We hold a real Supabase session but couldn't reach the API to verify
        // the invite (Render cold-start, flaky network). Don't drop the user to
        // the login form — show a retryable "verifying access" panel.
        setUser(null)
        setAccessMessage("Couldn't reach the server to verify your access. It may still be waking up.")
        setState('pending')
      }
    } finally {
      evaluating.current = false
    }
  }, [])

  // Register the bearer-token provider once, for the whole app.
  useEffect(() => {
    setAuthTokenProvider(currentAccessToken)
    return () => setAuthTokenProvider(null)
  }, [])

  useEffect(() => {
    if (!supabase) {
      setState('locked')
      return
    }
    void evaluate()
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_OUT') {
        setUser(null)
        setAccessMessage(null)
        setState('locked')
        return
      }
      // SIGNED_IN, TOKEN_REFRESHED, USER_UPDATED, INITIAL_SESSION
      void evaluate()
    })
    return () => data.subscription.unsubscribe()
  }, [evaluate])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      // A 401 slipped through mid-session — try one refresh, then re-evaluate.
      void (async () => {
        try {
          await supabase?.auth.refreshSession()
        } catch {
          /* fall through */
        }
        void evaluate()
      })()
    })
    return () => setUnauthorizedHandler(null)
  }, [evaluate])

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error('Auth is not configured.')
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password })
    if (error) throw new Error(error.message)
    // onAuthStateChange fires evaluate()
  }, [])

  const signUp = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error('Auth is not configured.')
    const { data, error } = await supabase.auth.signUp({ email: email.trim(), password })
    if (error) throw new Error(error.message)
    return { needsConfirmation: !data.session && !!data.user }
  }, [])

  const logout = useCallback(async () => {
    try {
      await supabase?.auth.signOut()
    } finally {
      setUser(null)
      setAccessMessage(null)
      setState('locked')
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        state,
        mode: 'supabase',
        user,
        accessMessage,
        loginPassphrase: notInThisMode('Passphrase sign-in'),
        signIn,
        signUp,
        recheck: () => void evaluate(),
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function AuthProvider({ children }: { children: ReactNode }) {
  return AUTH_MODE === 'supabase' ? (
    <SupabaseAuthProvider>{children}</SupabaseAuthProvider>
  ) : (
    <PassphraseAuthProvider>{children}</PassphraseAuthProvider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
