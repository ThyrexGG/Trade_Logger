import { useState } from 'react'
import { Link } from 'react-router-dom'
import { clearLossLimits, saveLossLimits } from '../api/lossLimits'
import { PageContainer } from '../components/shell/PageContainer'
import { SectionCard } from '../components/intelligence/primitives'
import { SectionError, SkeletonRows } from '../components/operations/primitives'
import { formatUsd } from '../lib/format'
import { useLossLimits } from '../lib/useLossLimits'
import { useToast } from '../lib/toast'
import type { LossLimitStatus } from '../types/lossLimits'

/** '' -> null (no limit), a number -> that number, anything else -> NaN. */
function parseLimit(raw: string): number | null {
  const t = raw.trim().replace(',', '.')
  if (!t) return null
  return /^\d+(\.\d+)?$/.test(t) ? Number(t) : Number.NaN
}

interface Verdict {
  text: string
  tone: 'positive' | 'warning' | 'negative'
}

function verdictOf(ratio: number | null, warnPct: number): Verdict | null {
  if (ratio == null) return null
  if (ratio >= 1) return { text: 'Limit reached', tone: 'negative' }
  if (ratio >= warnPct / 100) return { text: 'Close to limit', tone: 'warning' }
  return { text: 'OK', tone: 'positive' }
}

const TONE_TEXT = { positive: 'text-positive', warning: 'text-warning', negative: 'text-negative' } as const
const TONE_FILL = { positive: 'bg-positive', warning: 'bg-warning', negative: 'bg-negative' } as const

/** A progress bar to the limit, with a tick at the warning threshold. */
function LimitBar({ ratio, warnPct, label }: { ratio: number | null; warnPct: number; label: string }) {
  const verdict = verdictOf(ratio, warnPct)
  const pct = Math.max(0, Math.min(1, ratio ?? 0)) * 100
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3 text-sm text-primary">
        <span>{label}</span>
        {verdict ? <span className={`shrink-0 text-[11px] font-semibold uppercase tracking-wide ${TONE_TEXT[verdict.tone]}`}>{verdict.text}</span> : null}
      </div>
      <div
        className="relative h-2 overflow-hidden rounded-full bg-surface-elevated"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={label}
      >
        <div className={`h-full rounded-full ${verdict ? TONE_FILL[verdict.tone] : 'bg-muted'}`} style={{ width: `${pct}%` }} />
        <div className="absolute inset-y-0 w-px bg-border" style={{ left: `${warnPct}%` }} aria-hidden="true" />
      </div>
    </div>
  )
}

function AccountLimits({ s, warnPct, onChanged }: { s: LossLimitStatus; warnPct: number; onChanged: () => void }) {
  const toast = useToast()
  const [daily, setDaily] = useState(s.daily_loss_limit != null ? String(s.daily_loss_limit) : '')
  const [dd, setDd] = useState(s.drawdown_limit_pct != null ? String(s.drawdown_limit_pct) : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hasLimits = s.daily_loss_limit != null || s.drawdown_limit_pct != null

  async function save() {
    setError(null)
    const d = parseLimit(daily)
    const p = parseLimit(dd)
    if (Number.isNaN(d) || (d != null && d <= 0)) return setError('Daily loss limit must be a positive amount, or empty for none.')
    if (Number.isNaN(p) || (p != null && (p <= 0 || p >= 100))) return setError('Drawdown limit must be a percentage between 0 and 100, or empty for none.')
    setBusy(true)
    try {
      await saveLossLimits(s.account_id, { daily_loss: d, drawdown_pct: p })
      toast.success(`Limits saved for ${s.account_id} — you'll be notified at ${warnPct}% and at 100%`)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the limits.')
    } finally {
      setBusy(false)
    }
  }

  async function clear() {
    setBusy(true)
    setError(null)
    try {
      await clearLossLimits(s.account_id)
      setDaily('')
      setDd('')
      toast.success(`Limits cleared for ${s.account_id}`)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not clear the limits.')
    } finally {
      setBusy(false)
    }
  }

  const todayText =
    s.today_loss > 0 ? `down ${formatUsd(s.today_loss)}` : s.today_net_pnl > 0 ? `up ${formatUsd(s.today_net_pnl)}` : 'flat'

  return (
    <SectionCard title={s.account_id}>
      <div className="space-y-4">
        {s.daily_loss_limit != null ? (
          <LimitBar ratio={s.daily_ratio} warnPct={warnPct} label={`Today ${todayText} of ${formatUsd(s.daily_loss_limit)}`} />
        ) : null}

        {s.drawdown_limit_pct != null ? (
          s.drawdown_pct != null ? (
            <div className="space-y-1">
              <LimitBar ratio={s.drawdown_ratio} warnPct={warnPct} label={`${s.drawdown_pct.toFixed(1)}% below peak of ${s.drawdown_limit_pct}% limit`} />
              <p className="text-[11px] text-muted">
                Peak {formatUsd(s.peak_balance ?? 0)} · now {formatUsd(s.current_balance ?? 0)}
                {s.starting_balance_source === 'broker' ? ' · start worked out from your broker balance' : ''}
              </p>
            </div>
          ) : (
            <p className="text-xs text-warning">
              Drawdown needs a starting balance for this account. Open{' '}
              <Link to="/workspace/analytics" className="underline">Analytics</Link>, pick {s.account_id} and enter its
              starting balance, then it works.
            </p>
          )
        ) : null}

        {!hasLimits ? <p className="text-xs text-muted">No limits set for this account. Today: {formatUsd(s.today_net_pnl)}.</p> : null}

        <div className="grid gap-2.5 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-[11px] text-muted" htmlFor={`ll-daily-${s.account_id}`}>
            Daily loss limit ($)
            <input
              id={`ll-daily-${s.account_id}`}
              inputMode="decimal"
              value={daily}
              onChange={(e) => setDaily(e.target.value)}
              placeholder="none"
              disabled={busy}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted" htmlFor={`ll-dd-${s.account_id}`}>
            Drawdown limit (% below peak)
            <input
              id={`ll-dd-${s.account_id}`}
              inputMode="decimal"
              value={dd}
              onChange={(e) => setDd(e.target.value)}
              placeholder="none"
              disabled={busy}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
            />
          </label>
        </div>

        {error ? <p className="text-xs text-negative" role="alert">{error}</p> : null}

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void save()}
            disabled={busy}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
            style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
          >
            {busy ? 'Saving…' : 'Save limits'}
          </button>
          {hasLimits ? (
            <button
              type="button"
              onClick={() => void clear()}
              disabled={busy}
              className="rounded-lg border border-border px-3 py-1.5 text-xs text-secondary hover:bg-surface-hover disabled:opacity-40"
            >
              Clear
            </button>
          ) : null}
        </div>
      </div>
    </SectionCard>
  )
}

/**
 * Loss limits (`/workspace/loss-limits`): a daily-loss limit and a drawdown limit per account, with a
 * notification (phone, desktop, Telegram/Discord for the owner) when a closed trade takes you to 80% of a
 * limit and again at 100%. Notification only — it never closes or blocks a trade.
 */
export function LossLimitsPage() {
  const { state, data, error, refreshing, refetch } = useLossLimits()
  const warnPct = data?.warn_at_pct ?? 80

  return (
    <PageContainer
      title="Loss limits"
      description={`Set how much you are willing to lose in a day, and how far an account may fall from its peak. You are notified when a closed trade takes you to ${warnPct}% of a limit, and again when you reach it. It only tells you — it never closes or blocks a trade.`}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Refreshing…</span> : null}
          <button type="button" onClick={refetch} className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Refresh
          </button>
        </div>
      }
    >
      <div className="max-w-3xl space-y-4">
        {state === 'loading' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SkeletonRows rows={5} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError message={error ?? 'Could not load your limits.'} onRetry={refetch} />
          </div>
        ) : data ? (
          <div className="tl-fade-in space-y-4">
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing the last good numbers — refresh failed: {error}
              </p>
            ) : null}
            {data.accounts.length === 0 ? (
              <p className="text-sm text-muted">No accounts yet. Once you have trades (synced or logged by hand) they appear here.</p>
            ) : (
              data.accounts.map((a) => <AccountLimits key={a.account_id} s={a} warnPct={warnPct} onChanged={refetch} />)
            )}
            {data.note ? <p className="text-[11px] text-muted">{data.note}</p> : null}
          </div>
        ) : null}
      </div>
    </PageContainer>
  )
}
