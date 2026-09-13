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
import {
  exportAccount,
  listAccounts,
  listExports,
  removeAccount,
  restoreAccount,
  type AccountRowCounts,
  type ExportSnapshot,
} from '../api/accounts'
import { useToast } from '../lib/toast'
import { invalidateAllCaches } from '../lib/dataCache'
import { PARTNER_LINKS } from '../lib/partnerLinks'

/**
 * Every other page's data (Analytics, Journal, Command Center, ...) is served
 * from `dataCache`'s stale-while-revalidate cache, which has no way to know a
 * whole account's rows just got deleted or brought back server-side. Drop
 * every cached entry and fire the app's existing "data changed" signal so a
 * page that's currently open refetches immediately instead of showing rows
 * that no longer (or now again) exist.
 */
function announceAccountDataChanged() {
  invalidateAllCaches()
  window.dispatchEvent(new CustomEvent('tl:synced'))
}

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

            <PartnerLinksCard />

            <AddConnectionForm
              onAdded={() => {
                setNotice('Connection added.')
                void load()
              }}
              onError={setError}
            />
          </>
        )}

        <AccountDataDangerZone />
      </div>
    </PageContainer>
  )
}

/**
 * "Clear my data" — a clean slate for one account_id: exports a full JSON
 * snapshot to disk on the server, then deletes every row for that account
 * across closed_trades / open_positions / account_metadata / raw_deals /
 * price_alerts (account_management.py enforces export-before-delete, not
 * this component). Independent of the broker-connections feature above —
 * this works even when TL_CREDENTIAL_ENC_KEY isn't set, since it operates
 * on already-synced history, not stored credentials.
 *
 * Every clear leaves a snapshot behind that the "Recoverable snapshots"
 * section below can replay back in — restoring is additive (rows that
 * already exist are left alone), so it's safe to click more than once.
 */
function AccountDataDangerZone() {
  const toast = useToast()
  const [accounts, setAccounts] = useState<Record<string, AccountRowCounts>>({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [target, setTarget] = useState<string | null>(null)
  const [confirmText, setConfirmText] = useState('')
  const [busy, setBusy] = useState(false)

  const [exports, setExports] = useState<ExportSnapshot[]>([])
  const [exportsLoading, setExportsLoading] = useState(true)
  const [restoringPath, setRestoringPath] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await listAccounts(signal)
      if (signal?.aborted) return
      setAccounts(res.accounts ?? {})
      setLoadError(null)
    } catch (e) {
      if (!signal?.aborted) setLoadError(e instanceof Error ? e.message : 'Failed to load account data.')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  const loadExports = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await listExports(undefined, signal)
      if (signal?.aborted) return
      setExports(res.exports ?? [])
    } catch {
      /* the danger-zone card still works without this list; fail quiet */
    } finally {
      if (!signal?.aborted) setExportsLoading(false)
    }
  }, [])

  useEffect(() => {
    const c = new AbortController()
    void load(c.signal)
    void loadExports(c.signal)
    return () => c.abort()
  }, [load, loadExports])

  const openConfirm = (accountId: string) => {
    setTarget(accountId)
    setConfirmText('')
  }

  const clearAccount = async (accountId: string) => {
    setBusy(true)
    try {
      const { export_path } = await exportAccount(accountId)
      const { deleted_rows } = await removeAccount(accountId, export_path)
      const total = Object.values(deleted_rows).reduce((a, b) => a + b, 0)
      toast.success(`Cleared ${accountId}: ${total} row${total === 1 ? '' : 's'} deleted — snapshot saved, restorable below.`)
      setTarget(null)
      announceAccountDataChanged()
      await Promise.all([load(), loadExports()])
    } catch (e) {
      toast.error(e instanceof Error ? e.message : `Could not clear ${accountId}.`)
    } finally {
      setBusy(false)
    }
  }

  const restoreSnapshot = async (snapshot: ExportSnapshot) => {
    setRestoringPath(snapshot.export_path)
    try {
      const { restored_rows } = await restoreAccount(snapshot.export_path)
      const total = Object.values(restored_rows).reduce((a, b) => a + b, 0)
      if (total === 0) {
        toast.info(`Nothing to restore for ${snapshot.account_id} — it's already all back.`)
      } else {
        toast.success(`Restored ${snapshot.account_id}: ${total} row${total === 1 ? '' : 's'} brought back.`)
      }
      if (total > 0) announceAccountDataChanged()
      await load()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : `Could not restore ${snapshot.account_id}.`)
    } finally {
      setRestoringPath(null)
    }
  }

  const ids = Object.keys(accounts).sort()

  return (
    <div className="rounded-lg border border-negative/30 bg-negative/5">
      <div className="border-b border-negative/20 px-4 py-2 text-xs font-medium text-negative">
        Danger zone — clear account data
      </div>
      <div className="px-4 py-3">
        <p className="text-[11px] text-muted">
          Deletes every closed trade, open position, account snapshot, raw deal and price alert stored under an
          account. A snapshot is saved on the server first and listed under "Recoverable snapshots" below — clearing
          isn't permanent, restoring brings the exact rows back.
        </p>

        {loading ? (
          <p className="mt-3 text-xs text-muted">Loading…</p>
        ) : loadError ? (
          <p className="mt-3 rounded border border-negative/40 bg-negative/10 px-2 py-1 text-[11px] text-negative">
            {loadError}
          </p>
        ) : ids.length === 0 ? (
          <p className="mt-3 text-xs text-muted">No account data recorded yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-negative/10">
            {ids.map((id) => {
              const counts = accounts[id]
              const total = Object.values(counts).reduce((a, b) => a + b, 0)
              const breakdown = Object.entries(counts)
                .filter(([, n]) => n > 0)
                .map(([table, n]) => `${n} ${table.replace(/_/g, ' ')}`)
                .join(' · ')
              return (
                <li key={id} className="py-2.5">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-sm text-primary">{id}</div>
                      <div className="text-[11px] text-muted">{total} row{total === 1 ? '' : 's'} — {breakdown || 'nothing left'}</div>
                    </div>
                    <button
                      type="button"
                      disabled={busy || total === 0}
                      onClick={() => openConfirm(id)}
                      className="rounded border border-negative/40 px-2 py-1 text-xs text-negative hover:bg-negative/10 disabled:opacity-50"
                    >
                      Clear this account
                    </button>
                  </div>

                  {target === id ? (
                    <div className="mt-2 rounded border border-negative/30 bg-surface p-3">
                      <p className="text-[11px] text-secondary">
                        This deletes all {total} row{total === 1 ? '' : 's'} for{' '}
                        <span className="font-mono text-primary">{id}</span> (a snapshot is saved first — restorable
                        below). Type the account id to confirm.
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <input
                          value={confirmText}
                          onChange={(e) => setConfirmText(e.target.value)}
                          placeholder={id}
                          className="rounded border border-border bg-surface-elevated px-2 py-1 font-mono text-xs text-primary outline-none focus:border-negative"
                        />
                        <button
                          type="button"
                          disabled={busy || confirmText !== id}
                          onClick={() => void clearAccount(id)}
                          className="rounded bg-negative px-2.5 py-1 text-xs font-medium text-white disabled:opacity-40"
                        >
                          {busy ? 'Clearing…' : 'Delete permanently'}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => setTarget(null)}
                          className="rounded border border-border px-2.5 py-1 text-xs text-secondary hover:bg-surface-hover"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}

        <div className="mt-4 border-t border-negative/15 pt-3">
          <div className="text-xs font-medium text-secondary">Recoverable snapshots</div>
          <p className="mt-1 text-[11px] text-muted">
            Every "Clear this account" leaves one of these behind. Restoring is additive — rows that are already
            there are left alone, so it's safe to click more than once.
          </p>

          {exportsLoading ? (
            <p className="mt-2 text-xs text-muted">Loading…</p>
          ) : exports.length === 0 ? (
            <p className="mt-2 text-xs text-muted">No snapshots yet.</p>
          ) : (
            <ul className="mt-2 divide-y divide-border-subtle">
              {exports.map((snap) => {
                const total = Object.values(snap.row_counts).reduce((a, b) => a + b, 0)
                const restoring = restoringPath === snap.export_path
                return (
                  <li key={snap.export_path} className="flex flex-wrap items-center gap-3 py-2">
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-sm text-primary">{snap.account_id}</div>
                      <div className="text-[11px] text-muted">
                        {total} row{total === 1 ? '' : 's'} ·{' '}
                        {snap.exported_at ? new Date(snap.exported_at).toLocaleString() : 'unknown time'}
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={restoringPath !== null}
                      onClick={() => void restoreSnapshot(snap)}
                      className="rounded border border-border px-2 py-1 text-xs text-primary hover:bg-surface-hover disabled:opacity-50"
                    >
                      {restoring ? 'Restoring…' : 'Restore'}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Don't have a broker or funded account yet? — shown once, in the one spot
 * on the app where it's actually relevant (right where someone's about to
 * connect an account), never as a site-wide banner. See partnerLinks.ts for
 * how the "supports TradeLogger" copy only appears once a link is real.
 */
function PartnerLinksCard() {
  if (PARTNER_LINKS.length === 0) return null
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-xs font-medium text-secondary">Don't have an account yet?</div>
      <ul className="mt-2 space-y-2">
        {PARTNER_LINKS.map((p) => (
          <li key={p.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
            <a
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-accent hover:underline"
            >
              {p.name} →
            </a>
            <span className="text-[11px] text-muted">{p.blurb}</span>
          </li>
        ))}
      </ul>
      {PARTNER_LINKS.some((p) => p.isAffiliate) ? (
        <p className="mt-2 text-[10px] text-muted">
          Some links above are referral links — using them costs you nothing extra and helps keep TradeLogger running.
        </p>
      ) : null}
    </div>
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
