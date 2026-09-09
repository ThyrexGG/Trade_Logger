import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { PageContainer } from '../components/shell/PageContainer'
import { OpsSafetyBanner } from '../components/operations/primitives'
import {
  createConnection,
  deleteConnection,
  listConnections,
  syncConnection,
  testConnection,
  type BrokerConnection,
} from '../api/connections'

/**
 * Broker Connections (`/operations/connections`). Each user stores their own
 * Capital.com credentials here; they are encrypted at rest on the server and
 * never sent back to the browser. Read-only ingestion — "Sync now" pulls
 * history / balance / positions; nothing here places an order.
 */
export function ConnectionsPage() {
  const [rows, setRows] = useState<BrokerConnection[]>([])
  const [encOn, setEncOn] = useState(true)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await listConnections(signal)
      if (signal?.aborted) return
      setEncOn(res.encryption_configured)
      setRows(res.connections ?? [])
      setError(null)
    } catch (e) {
      if (!signal?.aborted) setError(e instanceof Error ? e.message : 'Failed to load connections.')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const c = new AbortController()
    load(c.signal)
    return () => c.abort()
  }, [load])

  const act = async (id: string, fn: () => Promise<{ ok?: boolean; detail?: string }>, verb: string) => {
    setBusy(id)
    setNotice(null)
    setError(null)
    try {
      const r = await fn()
      setNotice(`${verb}: ${r.ok ? 'OK' : (r.detail ?? 'failed')}`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : `${verb} failed.`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <PageContainer
      title="Broker Connections"
      description="Your Capital.com credentials, encrypted at rest on the server. Read-only — used only to pull trade history, balance and open positions."
      actions={
        <button
          type="button"
          onClick={() => void load()}
          className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
        >
          Refresh
        </button>
      }
    >
      <div className="space-y-4">
        <OpsSafetyBanner />

        {!encOn ? (
          <div className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
            Broker connections aren't enabled on this server (no encryption key configured).
            The owner sets <code className="text-primary">TL_CREDENTIAL_ENC_KEY</code> to turn this on.
          </div>
        ) : (
          <>
            {error ? (
              <p className="rounded border border-negative/40 bg-negative/10 px-3 py-2 text-xs text-negative" role="alert">
                {error}
              </p>
            ) : null}
            {notice ? (
              <p className="rounded border border-border bg-surface px-3 py-2 text-xs text-secondary" role="status">
                {notice}
              </p>
            ) : null}

            <div className="rounded-lg border border-border bg-surface">
              <div className="border-b border-border px-4 py-2 text-xs font-medium text-secondary">
                Your connections
              </div>
              {loading ? (
                <p className="px-4 py-4 text-sm text-muted">Loading…</p>
              ) : rows.length === 0 ? (
                <p className="px-4 py-4 text-sm text-muted">No connection yet — add one below.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {rows.map((r) => (
                    <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-primary">
                          {r.label || r.account_id || 'Capital.com'}{' '}
                          <span className="text-[11px] text-muted">
                            {r.is_demo ? 'demo' : 'live'}{r.is_active ? '' : ' · disabled'}
                          </span>
                        </div>
                        <div className="text-[11px] text-muted">
                          {r.last_sync_at
                            ? `last sync ${new Date(r.last_sync_at).toLocaleString()} · ${r.last_sync_ok ? 'ok' : 'failed'}`
                            : 'never synced'}
                          {r.last_error ? ` — ${r.last_error}` : ''}
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={busy === r.id}
                        onClick={() => void act(r.id, () => testConnection(r.id), 'Test')}
                        className="rounded border border-border px-2 py-1 text-xs text-primary hover:bg-surface-hover disabled:opacity-50"
                      >
                        Test
                      </button>
                      <button
                        type="button"
                        disabled={busy === r.id}
                        onClick={() => void act(r.id, () => syncConnection(r.id), 'Sync')}
                        className="rounded border border-border px-2 py-1 text-xs text-primary hover:bg-surface-hover disabled:opacity-50"
                      >
                        Sync now
                      </button>
                      <button
                        type="button"
                        disabled={busy === r.id}
                        onClick={() => {
                          if (confirm('Delete this connection? The stored credentials are erased.')) {
                            void act(r.id, () => deleteConnection(r.id), 'Delete')
                          }
                        }}
                        className="rounded border border-border px-2 py-1 text-xs text-negative hover:bg-surface-hover disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <AddConnectionForm
              onAdded={() => {
                setNotice('Connection added.')
                void load()
              }}
              onError={setError}
            />
          </>
        )}
      </div>
    </PageContainer>
  )
}

function AddConnectionForm({ onAdded, onError }: { onAdded: () => void; onError: (m: string) => void }) {
  const [label, setLabel] = useState('')
  const [accountId, setAccountId] = useState('')
  const [isDemo, setIsDemo] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy || !apiKey || !email || !password || !accountId) return
    setBusy(true)
    try {
      await createConnection({
        label,
        account_id: accountId,
        is_demo: isDemo,
        secret: { api_key: apiKey, email, password },
      })
      setApiKey('')
      setEmail('')
      setPassword('')
      setAccountId('')
      setLabel('')
      onAdded()
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Could not add the connection.')
    } finally {
      setBusy(false)
    }
  }

  const field = 'mt-1 w-full rounded border border-border bg-surface-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent'
  const lbl = 'block text-xs font-medium text-secondary'

  return (
    <form onSubmit={onSubmit} className="rounded-lg border border-border bg-surface p-4">
      <div className="text-xs font-medium text-secondary">Add a Capital.com connection</div>
      <p className="mt-1 text-[11px] text-muted">
        From Capital.com → Settings → API. Credentials are encrypted before they're stored and are never returned to the browser.
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <label className={lbl} htmlFor="c-label">Label (optional)</label>
          <input id="c-label" className={field} value={label} onChange={(e) => setLabel(e.target.value)} />
        </div>
        <div>
          <label className={lbl} htmlFor="c-acct">Account ID</label>
          <input id="c-acct" className={field} value={accountId} onChange={(e) => setAccountId(e.target.value)} />
        </div>
        <div>
          <label className={lbl} htmlFor="c-key">API key</label>
          <input id="c-key" className={field} value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoComplete="off" />
        </div>
        <div>
          <label className={lbl} htmlFor="c-email">Login email</label>
          <input id="c-email" type="email" className={field} value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
        </div>
        <div>
          <label className={lbl} htmlFor="c-pass">API password</label>
          <input id="c-pass" type="password" className={field} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </div>
        <label className="mt-6 flex items-center gap-2 text-xs text-secondary">
          <input type="checkbox" checked={isDemo} onChange={(e) => setIsDemo(e.target.checked)} />
          Demo account
        </label>
      </div>
      <button
        type="submit"
        disabled={busy || !apiKey || !email || !password || !accountId}
        className="mt-4 rounded bg-accent px-3 py-2 text-sm font-medium text-[var(--color-background)] disabled:opacity-50"
      >
        {busy ? 'Adding…' : 'Add connection'}
      </button>
    </form>
  )
}
