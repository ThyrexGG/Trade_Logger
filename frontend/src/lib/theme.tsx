import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

export type ThemeChoice = 'light' | 'dark' | 'system'
type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'tl.theme'

interface ThemeContextValue {
  /** What the visitor picked — 'system' means "follow the OS", the default. */
  choice: ThemeChoice
  /** What's actually painted right now, after resolving 'system'. */
  resolved: ResolvedTheme
  setChoice: (choice: ThemeChoice) => void
  /** Cycle system -> light -> dark -> system, for a single toggle button. */
  cycle: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function readStored(): ThemeChoice {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

function systemPrefersLight(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: light)').matches
}

/**
 * Applies the resolved theme to `<html data-theme>` (tokens.css keys off
 * that attribute) and mirrors it to localStorage + the `theme-color` meta
 * tags so the browser chrome matches too. Mounted once near the root.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(() => readStored())
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    choice === 'system' ? (systemPrefersLight() ? 'light' : 'dark') : choice,
  )

  const apply = useCallback((next: ThemeChoice) => {
    const root = document.documentElement
    if (next === 'system') {
      root.removeAttribute('data-theme')
      setResolved(systemPrefersLight() ? 'light' : 'dark')
    } else {
      root.setAttribute('data-theme', next)
      setResolved(next)
    }
  }, [])

  useEffect(() => {
    apply(choice)
  }, [choice, apply])

  // Live-follow the OS while on 'system' (no reload needed to react to it).
  useEffect(() => {
    if (choice !== 'system' || typeof window === 'undefined') return
    const mq = window.matchMedia('(prefers-color-scheme: light)')
    const onChange = () => setResolved(mq.matches ? 'light' : 'dark')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [choice])

  const setChoice = useCallback((next: ThemeChoice) => {
    setChoiceState(next)
    try {
      if (next === 'system') localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* private browsing / storage blocked — the choice just won't persist */
    }
  }, [])

  const cycle = useCallback(() => {
    setChoice(choice === 'system' ? 'light' : choice === 'light' ? 'dark' : 'system')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [choice])

  return (
    <ThemeContext.Provider value={{ choice, resolved, setChoice, cycle }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within <ThemeProvider>')
  return ctx
}
