import { useState, type FormEvent } from 'react'
import { useAuth } from '../../lib/auth'

/**
 * Full-screen passphrase gate shown when the server requires auth and this
 * browser has no valid session. Nothing else in the app renders behind it.
 */
export function LoginScreen() {
  const { login } = useAuth()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy || !password) return
    setBusy(true)
    setError(null)
    try {
      await login(password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-lg border border-border bg-surface p-6 shadow-lg"
      >
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
    </div>
  )
}
