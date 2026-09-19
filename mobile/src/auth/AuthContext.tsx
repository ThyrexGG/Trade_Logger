import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { getMe, login as apiLogin, logout as apiLogout } from '../api/auth'
import { ApiError, setTokenProvider, setUnauthorizedHandler } from '../api/client'
import type { AuthUser } from '../types/auth'
import { clearSession, loadSession, saveSession } from './storage'

type Status = 'loading' | 'signedOut' | 'signedIn'

interface AuthValue {
  status: Status
  user: AuthUser | null
  /** why the user was bounced to the login screen ("Your session has ended…"), if they were */
  notice: string | null
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

/**
 * Owns the login session. The bearer token lives in a ref (so the API client
 * can read it synchronously) and is mirrored to the phone's secure storage so
 * the user stays signed in across app restarts.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const tokenRef = useRef<string | null>(null)

  const endSession = useCallback(async (message: string | null) => {
    tokenRef.current = null
    setUser(null)
    setNotice(message)
    setStatus('signedOut')
    await clearSession()
  }, [])

  useEffect(() => {
    setTokenProvider(() => tokenRef.current)
    setUnauthorizedHandler(() => {
      if (tokenRef.current) void endSession('Your session has ended. Sign in again.')
    })
    return () => {
      setTokenProvider(null)
      setUnauthorizedHandler(null)
    }
  }, [endSession])

  // Restore a saved session on app start.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const stored = await loadSession()
      if (cancelled) return
      if (!stored) {
        setStatus('signedOut')
        return
      }
      tokenRef.current = stored.token
      try {
        const me = await getMe()
        if (cancelled) return
        if (me.authenticated && me.user) {
          setUser(me.user)
          setStatus('signedIn')
          void saveSession(stored.token, me.user)
        } else {
          await endSession(me.error ?? 'Your session has ended. Sign in again.')
        }
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          await endSession('Your session has ended. Sign in again.')
        } else {
          // Offline / server hiccup: keep the saved login rather than throwing the user out.
          setUser(stored.user)
          setStatus('signedIn')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [endSession])

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await apiLogin(email.trim(), password)
    if (!result.ok || !result.token) {
      throw new ApiError(result.error ?? 'Sign-in failed.', 401)
    }
    tokenRef.current = result.token
    await saveSession(result.token, result.user)
    setUser(result.user)
    setNotice(null)
    setStatus('signedIn')
  }, [])

  const signOut = useCallback(async () => {
    try {
      await apiLogout() // revoke server-side; ignore failures (offline logout still clears the phone)
    } catch {
      /* best effort */
    }
    await endSession(null)
  }, [endSession])

  const value = useMemo(() => ({ status, user, notice, signIn, signOut }), [status, user, notice, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
