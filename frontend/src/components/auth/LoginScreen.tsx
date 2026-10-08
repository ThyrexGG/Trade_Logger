import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { forgotPassword, resetPassword } from '../../api/auth'
import { ApiError } from '../../api/client'
import { useAuth } from '../../lib/auth'
import { BrandLockup } from '../shell/BrandMark'

/**
 * Full-screen gate shown when the app is locked. Renders one of three things:
 *  - passphrase mode  → the single-user passphrase form (W3)
 *  - multiuser mode / locked  → email + password, with a "create account" toggle
 *  - multiuser mode / pending → signed in, but this email is not invited yet
 */
export function LoginScreen() {
  const { mode } = useAuth()
  const [searchParams] = useSearchParams()
  const resetToken = searchParams.get('reset_token')
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--color-background)] px-4 py-10">
      <BrandLockup />
      <p className="tl-label mt-3">Trading journal · analytics · market context</p>

      <div className="tl-card mt-6 w-full max-w-sm p-6">
        {mode === 'multiuser' && resetToken ? (
          <ResetPasswordForm token={resetToken} />
        ) : mode === 'multiuser' ? (
          <MultiUserForm />
        ) : (
          <PassphraseForm />
        )}
      </div>

      <p className="mt-4 w-full max-w-sm text-center text-[11px] leading-relaxed text-muted">
        By continuing you agree to the{' '}
        <Link to="/legal/terms" className="underline hover:text-primary">
          Terms
        </Link>{' '}
        and{' '}
        <Link to="/legal/privacy" className="underline hover:text-primary">
          Privacy Policy
        </Link>
        . TradeLogger is a personal journal, not financial advice.
      </p>
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
      <h1 className="text-base font-semibold text-primary">Welcome back</h1>
      <p className="mt-1 text-xs text-muted">
        Enter your passphrase to continue.
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
        className="tl-input mt-1 w-full"
      />

      {error ? (
        <p className="mt-2 text-xs text-negative" role="alert">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy || !password}
        className="tl-btn tl-btn--primary tl-btn--lg mt-5 w-full"
      >
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  )
}

function MultiUserForm() {
  const { state, accessMessage, signIn, signUp, recheck, logout, signupOpen } = useAuth()

  const [tab, setTab] = useState<'signin' | 'signup' | 'forgot'>('signin')
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
        {!accessMessage?.toLowerCase().includes('reach the server') ? (
          <p className="mt-2 text-xs text-muted">
            Ask the owner to add your email to the invite list, then retry.
          </p>
        ) : null}
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => recheck()}
            className="tl-btn tl-btn--primary flex-1"
          >
            Retry
          </button>
          <button
            type="button"
            onClick={() => void logout()}
            className="tl-btn tl-btn--secondary"
          >
            Sign out
          </button>
        </div>
      </div>
    )
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (tab === 'forgot') {
      if (busy || !email) return
      setBusy(true)
      setError(null)
      setNotice(null)
      try {
        await forgotPassword(email)
      } catch {
        // forgotPassword always resolves {ok:true} from the server; a throw
        // here means the request itself failed (network/server down), not
        // that the email was invalid — show the same notice either way so
        // nothing about the email's validity leaks from this form either.
      } finally {
        setBusy(false)
        setNotice("If that email has an account, we've sent a reset link.")
      }
      return
    }

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

  if (tab === 'forgot') {
    return (
      <form onSubmit={onSubmit}>
        <h1 className="text-base font-semibold text-primary">Reset your password</h1>
        <p className="mt-1 text-xs text-muted">
          Enter your account email — we'll send a link to set a new password.
        </p>

        <label htmlFor="tl-forgot-email" className="mt-4 block text-xs font-medium text-secondary">
          Email
        </label>
        <input
          id="tl-forgot-email"
          type="email"
          autoFocus
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="tl-input mt-1 w-full"
        />

        {notice ? (
          <p className="mt-2 text-xs text-positive" role="status">
            {notice}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={busy || !email}
          className="tl-btn tl-btn--primary tl-btn--lg mt-5 w-full"
        >
          {busy ? 'Sending…' : 'Send reset link'}
        </button>

        <button
          type="button"
          onClick={() => {
            setTab('signin')
            setNotice(null)
          }}
          className="mt-3 w-full text-center text-xs text-muted underline hover:text-primary"
        >
          Back to sign in
        </button>
      </form>
    )
  }

  return (
    <form onSubmit={onSubmit}>
      <h1 className="text-base font-semibold text-primary">{tab === 'signup' ? 'Create your account' : 'Welcome back'}</h1>
      <p className="mt-1 text-xs text-muted">
        {signupOpen ? 'Your private trading journal.' : 'Your private trading journal. Invite-only for now.'}
      </p>

      <div className="tl-seg mt-4 grid w-full grid-cols-2" role="tablist" aria-label="Sign in or create an account">
        {(['signin', 'signup'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => {
              setTab(t)
              setError(null)
              setNotice(null)
            }}
            role="tab"
            aria-selected={tab === t}
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
        className="tl-input mt-1 w-full"
      />

      <div className="mt-3 flex items-baseline justify-between">
        <label htmlFor="tl-pw" className="block text-xs font-medium text-secondary">
          Password
        </label>
        {tab === 'signin' ? (
          <button
            type="button"
            onClick={() => {
              setTab('forgot')
              setError(null)
              setNotice(null)
            }}
            className="text-xs text-muted underline hover:text-primary"
          >
            Forgot password?
          </button>
        ) : null}
      </div>
      <input
        id="tl-pw"
        type="password"
        autoComplete={tab === 'signup' ? 'new-password' : 'current-password'}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="tl-input mt-1 w-full"
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
        className="tl-btn tl-btn--primary tl-btn--lg mt-5 w-full"
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

function ResetPasswordForm({ token }: { token: string }) {
  const { recheck } = useAuth()
  const [, setSearchParams] = useSearchParams()
  // Through the router, not history.replaceState — otherwise the router's own
  // location keeps the token and the form reappears after a later logout.
  const dropToken = () =>
    setSearchParams(
      (prev) => {
        prev.delete('reset_token')
        return prev
      },
      { replace: true },
    )
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy || !password) return
    if (password !== confirm) {
      setError("Passwords don't match.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await resetPassword(token, password)
      setDone(true)
      // The reset call already set the session cookie, so re-checking auth
      // lands the user straight in.
      dropToken()
      recheck()
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : 'Could not reset your password.',
      )
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div>
        <h1 className="text-base font-semibold text-primary">Password updated</h1>
        <p className="mt-2 text-xs text-muted">You're signed in. Loading TradeLogger…</p>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit}>
      <h1 className="text-base font-semibold text-primary">Set a new password</h1>
      <p className="mt-1 text-xs text-muted">Choose a new password for your account.</p>

      <label htmlFor="tl-reset-pw" className="mt-4 block text-xs font-medium text-secondary">
        New password
      </label>
      <input
        id="tl-reset-pw"
        type="password"
        autoFocus
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="tl-input mt-1 w-full"
      />

      <label htmlFor="tl-reset-pw2" className="mt-3 block text-xs font-medium text-secondary">
        Confirm new password
      </label>
      <input
        id="tl-reset-pw2"
        type="password"
        autoComplete="new-password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        className="tl-input mt-1 w-full"
      />

      {error ? (
        <p className="mt-2 text-xs text-negative" role="alert">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy || !password || !confirm}
        className="tl-btn tl-btn--primary tl-btn--lg mt-5 w-full"
      >
        {busy ? 'Saving…' : 'Set new password'}
      </button>

      <button
        type="button"
        onClick={dropToken}
        className="mt-3 w-full text-center text-xs text-muted underline hover:text-primary"
      >
        Back to sign in
      </button>
    </form>
  )
}
