import { useState, type FormEvent } from 'react'
import { useAuth } from '../../lib/auth'

/**
 * Full-screen gate shown when the app is locked. Renders one of three things:
 *  - passphrase mode  → the single-user passphrase form (W3)
 *  - supabase mode / locked  → email + password, with a "create account" toggle
 *  - supabase mode / pending → signed in, but this email is not invited yet
 */
export function LoginScreen() {
  const { mode } = useAuth()
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-6 shadow-lg">
        {mode === 'supabase' ? <SupabaseForm /> : <PassphraseForm />}
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
        className="mt-1 w-full rounded border border-border bg-surface-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
      />

      {error ? (
        <p className="mt-2 text-xs text-negative" role="alert">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy || !password}
        className="mt-4 w-full rounded bg-accent px-3 py-2 text-sm font-medium text-[var(--color-background)] disabled:opacity-50"
      >
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  )
}

function SupabaseForm() {
  const { state, accessMessage, signIn, signUp, recheck, logout } = useAuth()

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
            className="flex-1 rounded bg-accent px-3 py-2 text-sm font-medium text-[var(--color-background)]"
          >
            Retry
          </button>
          <button
            type="button"
            onClick={() => void logout()}
            className="rounded border border-border px-3 py-2 text-sm text-muted hover:text-primary"
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
      <p className="mt-1 text-xs text-muted">Private trading journal. Invite-only.</p>

      <div className="mt-4 flex rounded border border-border p-0.5 text-xs">
        {(['signin', 'signup'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => {
              setTab(t)
              setError(null)
              setNotice(null)
            }}
            className={`flex-1 rounded px-2 py-1 font-medium ${
              tab === t ? 'bg-accent text-[var(--color-background)]' : 'text-muted'
            }`}
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
        className="mt-1 w-full rounded border border-border bg-surface-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
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
        className="mt-1 w-full rounded border border-border bg-surface-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
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
        className="mt-4 w-full rounded bg-accent px-3 py-2 text-sm font-medium text-[var(--color-background)] disabled:opacity-50"
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
