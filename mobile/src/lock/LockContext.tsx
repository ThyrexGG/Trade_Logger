import AsyncStorage from '@react-native-async-storage/async-storage'
import * as LocalAuthentication from 'expo-local-authentication'
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { AppState } from 'react-native'
import { isLockSuspended } from './suspend'

const ENABLED_KEY = 'tl.lock.enabled'
/** Re-lock only after the app has been away this long (quick app-switches don't nag). */
const LOCK_AFTER_MS = 30_000

interface LockValue {
  /** preference has been read; render nothing sensitive until this is true */
  ready: boolean
  enabled: boolean
  locked: boolean
  /** device has biometrics or a passcode set up */
  available: boolean
  unlock: () => Promise<void>
  /** drop the locked state without prompting (used when the user signs out, so the next sign-in is not gated) */
  clearLocked: () => void
  /** turn the lock on/off; turning on first proves the user can actually authenticate */
  setEnabled: (on: boolean) => Promise<string | null>
}

const Ctx = createContext<LockValue | null>(null)

export function useLock(): LockValue {
  const v = useContext(Ctx)
  if (!v) throw new Error('useLock must be used inside <LockProvider>')
  return v
}

async function authenticate(prompt: string): Promise<boolean> {
  try {
    const r = await LocalAuthentication.authenticateAsync({ promptMessage: prompt, cancelLabel: 'Cancel' })
    return r.success
  } catch {
    return false
  }
}

/** Optional Face ID / fingerprint / passcode gate over the whole signed-in app. */
export function LockProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [enabled, setEnabledState] = useState(false)
  const [locked, setLocked] = useState(false)
  const [available, setAvailable] = useState(false)
  const enabledRef = useRef(false)
  const leftAt = useRef<number | null>(null)
  const prompting = useRef(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      let on = false
      try {
        on = (await AsyncStorage.getItem(ENABLED_KEY)) === '1'
      } catch {
        /* default off */
      }
      let avail = false
      try {
        avail = await LocalAuthentication.hasHardwareAsync().then(async (hw) => hw && (await LocalAuthentication.isEnrolledAsync()))
      } catch {
        /* treat as unavailable */
      }
      if (cancelled) return
      // A saved "on" with no way to authenticate would lock the user out forever — ignore it.
      const effective = on && avail
      enabledRef.current = effective
      setEnabledState(effective)
      setAvailable(avail)
      setLocked(effective) // cold start: locked until authenticated
      setReady(true)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'background') {
        if (!isLockSuspended()) leftAt.current = Date.now()
      } else if (next === 'active') {
        const left = leftAt.current
        leftAt.current = null
        if (enabledRef.current && left !== null && !prompting.current && Date.now() - left >= LOCK_AFTER_MS) {
          setLocked(true)
        }
      }
    })
    return () => sub.remove()
  }, [])

  const unlock = useCallback(async () => {
    if (prompting.current) return
    prompting.current = true
    try {
      if (await authenticate('Unlock TradeLogger')) setLocked(false)
    } finally {
      prompting.current = false
    }
  }, [])

  const clearLocked = useCallback(() => setLocked(false), [])

  const setEnabled = useCallback(async (on: boolean): Promise<string | null> => {
    if (on) {
      prompting.current = true
      const ok = await authenticate('Confirm to turn on app lock')
      prompting.current = false
      if (!ok) return 'Could not verify it is you, so the lock stays off.'
    }
    enabledRef.current = on
    setEnabledState(on)
    try {
      await AsyncStorage.setItem(ENABLED_KEY, on ? '1' : '0')
    } catch {
      /* preference just won't survive a restart */
    }
    return null
  }, [])

  const value = useMemo(
    () => ({ ready, enabled, locked, available, unlock, clearLocked, setEnabled }),
    [ready, enabled, locked, available, unlock, clearLocked, setEnabled],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
