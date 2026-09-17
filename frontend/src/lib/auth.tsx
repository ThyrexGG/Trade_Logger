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
  /** multiuser mode only — true once the server has opened sign-up to
   * anyone (TL_SIGNUP_OPEN=1), not just the invite allowlist. */
  signupOpen: boolean
  /** multiuser mode only — true while `state === 'authed'` is being served
   * from a cached session because the server couldn't be reached (e.g. a
   * Render cold-start), not from a fresh confirmed check. The app stays
   * fully usable; the existing API-health pill already signals the outage,
   * and a background recheck clears this the moment the server answers. */
  degraded: boolean
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
        signupOpen: false,
        degraded: false,
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

const SESSION_CACHE_KEY = 'tl.auth.lastSession'
// How long a cached "you were logged in" fact is trusted while the server is
// unreachable. Long enough to ride out a cold-start or a rough patch of
// connectivity; short enough that this is never mistaken for real offline
// support. A cookie the server has actually revoked still gets caught the
// moment a request succeeds again (see the success branch of evaluate()).
const SESSION_CACHE_GRACE_MS = 24 * 60 * 60 * 1000
const DEGRADED_RECHECK_MS = 20_000

function readCachedSession(): AuthUser | null {
  try {
    const raw = localStorage.getItem(SESSION_CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { user: AuthUser; cachedAt: number }
    if (Date.now() - parsed.cachedAt > SESSION_CACHE_GRACE_MS) return null
    return parsed.user
  } catch {
    return null
  }
}

function writeCachedSession(user: AuthUser | null): void {
  try {
    if (user) {
      localStorage.setItem(SESSION_CACHE_KEY, JSON.stringify({ user, cachedAt: Date.now() }))
    } else {
      localStorage.removeItem(SESSION_CACHE_KEY)
    }
  } catch {
    /* private browsing / storage blocked — just skip the fallback */
  }
}

function MultiUserAuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [accessMessage, setAccessMessage] = useState<string | null>(null)
  const [signupOpen, setSignupOpen] = useState(false)
  const [degraded, setDegraded] = useState(false)
  // The in-flight request for the current evaluate() call. A new call aborts
  // whatever's still running instead of no-op'ing — otherwise a single hung
  // fetch (e.g. mid Render/Cloudflare cold-start) leaves Retry permanently
  // dead until the page is reloaded.
  const inFlight = useRef<AbortController | null>(null)

  const evaluate = useCallback(async () => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    // getMe() itself never times out, so cap it client-side — otherwise a
    // stalled connection can sit for minutes before the OS gives up.
    const timeoutId = setTimeout(() => controller.abort(), 15_000)
    try {
      const me = await getMe(controller.signal)
      if (inFlight.current !== controller) return // superseded by a newer call
      setSignupOpen(me.signup_open)
      if (me.authenticated && me.user) {
        setUser(me.user)
        setAccessMessage(null)
        setState('authed')
        setDegraded(false)
        writeCachedSession(me.user)
      } else if (me.error) {
        // A session exists but is not usable (ended, or not invited) — the
        // server actually answered, so any cached fallback is now stale.
        setUser(null)
        setAccessMessage(me.error)
        setState(me.error.toLowerCase().includes('invite') ? 'pending' : 'locked')
        setDegraded(false)
        writeCachedSession(null)
      } else {
        setUser(null)
        setAccessMessage(null)
        setState('locked')
        setDegraded(false)
        writeCachedSession(null)
      }
    } catch {
      if (inFlight.current !== controller) return // superseded by a newer call
      // Couldn't reach the API at all (Render cold-start, flaky network) —
      // this says nothing about whether the session is still valid. Fall
      // back to the last confirmed login instead of locking the whole app
      // out; the TopBar's API-health pill already shows the outage, and the
      // periodic recheck below reconciles with the real state once the
      // server responds again.
      const cached = readCachedSession()
      if (cached) {
        setUser(cached)
        setAccessMessage(null)
        setState('authed')
        setDegraded(true)
      } else {
        setUser(null)
        setAccessMessage("Couldn't reach the server. It may still be waking up.")
        setState('pending')
      }
    } finally {
      clearTimeout(timeoutId)
    }
  }, [])

  useEffect(() => {
    void evaluate()
  }, [evaluate])

  // While running on the cached fallback, keep quietly retrying in the
  // background so a real logout (or the server coming back with different
  // news) is picked up without the user having to do anything.
  useEffect(() => {
    if (!degraded) return
    const timer = window.setInterval(() => {
      if (!document.hidden) void evaluate()
    }, DEGRADED_RECHECK_MS)
    return () => window.clearInterval(timer)
  }, [degraded, evaluate])

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
      setDegraded(false)
      writeCachedSession(null)
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        state,
        mode: 'multiuser',
        user,
        accessMessage,
        signupOpen,
        degraded,
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
