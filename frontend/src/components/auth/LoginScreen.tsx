import { useState, type FormEvent } from 'react'
import { useAuth } from '../../lib/auth'

/**
 * Full-screen gate shown when the app is locked. Renders one of three things:
 *  - passphrase mode  → the single-user passphrase form (W3)
 *  - multiuser mode / locked  → email + password, with a "create account" toggle
 *  - multiuser mode / pending → signed in, but this email is not invited yet
 */
export function LoginScreen() {
  const { mode } = useAuth()
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--color-background)] px-4">
      {/* Same glow-blob backdrop as the app shell (AppShell.tsx) — this
         screen renders before the shell, so it needs its own copy for the
         glass card below to have something to actually blur. Subtle on
         purpose: a faint warm ambient glow behind an otherwise-black card,
         not color visibly bleeding through it (the premium black-and-gold
         fintech reference reads as mostly-black, gold as accent only). */}
      <div className="pointer-events-none absolute inset-0 z-0" aria-hidden="true">
        <div
          className="absolute left-[22%] top-[8%] h-[60vh] w-[60vh] rounded-full opacity-[0.18]"
          style={{ background: 'radial-gradient(circle, var(--tl-glow-a) 0%, transparent 65%)' }}
        />
        <div
          className="absolute right-[18%] bottom-[5%] h-[60vh] w-[60vh] rounded-full opacity-[0.14]"
          style={{ background: 'radial-gradient(circle, var(--tl-glow-b) 0%, transparent 65%)' }}
        />
      </div>

      <div
        className="relative z-10 w-full max-w-sm rounded-2xl p-6 backdrop-blur-xl"
        style={{
          background: 'var(--tl-glass-bg)',
          border: '1px solid var(--tl-glass-border)',
          boxShadow: '0 20px 50px var(--tl-glass-shadow), inset 0 1px 0 var(--tl-glass-highlight)',
        }}
      >
        {mode === 'multiuser' ? <MultiUserForm /> : <PassphraseForm />}
      </div>
    </div>
  )
}

function PassphraseForm() {
  const { loginPassphrase } = useAuth()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy || !password) return
    setBusy(true)
    setError(null)
    try {
      await loginPassphrase(password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h1 className="text-base font-semibold text-primary">TradeLogger</h1>
      <p className="mt-1 text-xs text-muted">
        Private research &amp; journal terminal. Enter your passphrase to continue.
      </p>

      <label htmlFor="tl-pass" className="mt-5 block text-xs font-medium text-secondary">
        Passphrase
      </label>
      <input
        id="tl-pass"
        type="password"
        autoFocus
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="mt-1 w-full rounded-xl border border-border bg-surface-elevated/60 px-3.5 py-2.5 text-sm text-primary outline-none focus:border-accent"
      />

      {error ? (
        <p className="mt-2 text-xs text-negative" role="alert">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy || !password}
        className="mt-4 w-full rounded-xl px-3 py-2.5 text-sm font-semibold shadow-lg disabled:opacity-50"
        style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
      >
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  )
}

function MultiUserForm() {
  const { state, accessMessage, signIn, signUp, recheck, logout, signupOpen } = useAuth()

  const [tab, setTab] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  if (state === 'pending') {
    return (
      <div>
        <h1 className="text-base font-semibold text-primary">Almost there</h1>
        <p className="mt-2 text-xs text-muted">{accessMessage}</p>
        <p className="mt-2 text-xs text-muted">
          Ask the owner to add your email to the invite list, then retry.
        </p>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => recheck()}
            className="flex-1 rounded-xl px-3 py-2.5 text-sm font-semibold shadow-lg"
            style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
          >
            Retry
          </button>
          <button
            type="button"
            onClick={() => void logout()}
            className="rounded-xl border border-border px-3 py-2.5 text-sm text-muted hover:text-primary"
          >
            Sign out
          </button>
        </div>
      </div>
    )
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy || !email || !password) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      if (tab === 'signup') {
        const { needsConfirmation } = await signUp(email, password)
        if (needsConfirmation) {
          setNotice('Check your email for a confirmation link, then sign in.')
          setTab('signin')
          setPassword('')
        }
      } else {
        await signIn(email, password)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h1 className="text-base font-semibold text-primary">TradeLogger</h1>
      <p className="mt-1 text-xs text-muted">
        {signupOpen ? 'Private trading journal.' : 'Private trading journal. Invite-only.'}
      </p>

      <div className="mt-4 flex rounded-xl border border-border p-1 text-xs">
        {(['signin', 'signup'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => {
              setTab(t)
              setError(null)
              setNotice(null)
            }}
            className={`flex-1 rounded-lg px-2 py-1.5 font-medium transition-colors ${
              tab === t ? 'shadow' : 'text-muted'
            }`}
            style={
              tab === t
                ? { background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }
                : undefined
            }
          >
            {t === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        ))}
      </div>

      <label htmlFor="tl-email" className="mt-4 block text-xs font-medium text-secondary">
        Email
      </label>
      <input
        id="tl-email"
        type="email"
        autoFocus
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="mt-1 w-full rounded-xl border border-border bg-surface-elevated/60 px-3.5 py-2.5 text-sm text-primary outline-none focus:border-accent"
      />

      <label htmlFor="tl-pw" className="mt-3 block text-xs font-medium text-secondary">
        Password
      </label>
      <input
        id="tl-pw"
        type="password"
        autoComplete={tab === 'signup' ? 'new-password' : 'current-password'}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="mt-1 w-full rounded-xl border border-border bg-surface-elevated/60 px-3.5 py-2.5 text-sm text-primary outline-none focus:border-accent"
      />

      {error ? (
        <p className="mt-2 text-xs text-negative" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="mt-2 text-xs text-positive" role="status">
          {notice}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy || !email || !password}
        className="mt-4 w-full rounded-xl px-3 py-2.5 text-sm font-semibold shadow-lg disabled:opacity-50"
        style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
      >
        {busy
          ? tab === 'signup'
            ? 'Creating…'
            : 'Signing in…'
          : tab === 'signup'
            ? 'Create account'
            : 'Sign in'}
      </button>
    </form>
  )
}
