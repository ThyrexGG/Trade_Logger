import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  getAuthStatus,
  getMe,
  login as apiLogin,
  logout as apiLogout,
  signup as apiSignup,
  type AuthMode,
  type AuthUser,
} from '../api/auth'
import { ApiError, setUnauthorizedHandler } from '../api/client'
import { AUTH_MODE } from './supabase'

/**
 * loading = still checking · open = no auth configured · authed = logged in ·
 * locked = sign-in required · pending = signed in but this email is not on the
 * invite list yet (or access could not be verified).
 */
type AuthState = 'loading' | 'open' | 'authed' | 'locked' | 'pending'

interface AuthContextValue {
  state: AuthState
  mode: AuthMode
  user: AuthUser | null
  /** Set when state === 'pending' — why access is not granted. */
  accessMessage: string | null
  /** passphrase mode */
  loginPassphrase: (password: string) => Promise<void>
  /** multiuser mode */
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>
  /** multiuser mode — re-check access (the "pending" retry button) */
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
      await apiLogin(password)
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
// Multi-user mode (W10) — invite-only email + password, first-party.
// The session is an httpOnly cookie set by the API; there is no client token.
// ---------------------------------------------------------------------------

function MultiUserAuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [accessMessage, setAccessMessage] = useState<string | null>(null)
  const evaluating = useRef(false)

  const evaluate = useCallback(async () => {
    if (evaluating.current) return
    evaluating.current = true
    try {
      const me = await getMe()
      if (me.authenticated && me.user) {
        setUser(me.user)
        setAccessMessage(null)
        setState('authed')
      } else if (me.error) {
        // A session exists but is not usable (ended, or not invited).
        setUser(null)
        setAccessMessage(me.error)
        setState(me.error.toLowerCase().includes('invite') ? 'pending' : 'locked')
      } else {
        setUser(null)
        setAccessMessage(null)
        setState('locked')
      }
    } catch {
      // Couldn't reach the API (Render cold-start, flaky network). Don't force
      // the login form — offer a retry.
      setUser(null)
      setAccessMessage("Couldn't reach the server. It may still be waking up.")
      setState('pending')
    } finally {
      evaluating.current = false
    }
  }, [])

  useEffect(() => {
    void evaluate()
  }, [evaluate])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      setState('locked')
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  const signIn = useCallback(
    async (email: string, password: string) => {
      try {
        await apiLogin(password, email.trim())
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          setAccessMessage(err.message)
          setState('pending')
          return
        }
        throw err // 401/429 -> the form shows the message
      }
      await evaluate()
    },
    [evaluate],
  )

  const signUp = useCallback(
    async (email: string, password: string) => {
      try {
        await apiSignup(email.trim(), password)
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          setAccessMessage(err.message)
          setState('pending')
          return { needsConfirmation: false }
        }
        throw err // 409 (email taken) / 422 (weak) -> the form shows the message
      }
      await evaluate()
      return { needsConfirmation: false }
    },
    [evaluate],
  )

  const logout = useCallback(async () => {
    try {
      await apiLogout()
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
        mode: 'multiuser',
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
  return AUTH_MODE === 'multiuser' ? (
    <MultiUserAuthProvider>{children}</MultiUserAuthProvider>
  ) : (
    <PassphraseAuthProvider>{children}</PassphraseAuthProvider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
