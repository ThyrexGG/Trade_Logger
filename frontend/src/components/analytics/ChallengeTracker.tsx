import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  advanceChallengePhase,
  deleteChallengeConfig,
  getChallengeStatus,
  resetChallenge,
  saveChallengeConfig,
} from '../../api/challenge'
import { SectionCard } from '../intelligence/primitives'
import { DisclaimerNote } from '../shared/DisclaimerNote'
import type { ChallengeConfig, ChallengeConfigInput, ChallengeStatus } from '../../types/challenge'
import { describeAccount } from '../../lib/accountLabel'
import { formatUsd } from '../../lib/format'
import { amountsHidden } from '../../lib/privacy'
import { todayIso } from '../../lib/dates'

const money = (n: number | null) =>
  n === null ? '—' : amountsHidden() ? formatUsd(n) : n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

// Not every linked account is a prop-firm challenge (a personal Capital.com account, say) — this hides the
// "set up a challenge" invitation for one specific account without a server round-trip. Purely a display
// preference (like the account filter itself), so it lives in localStorage, per account.
function hideKey(acc: string): string {
  return `tl.analytics.challengeHidden.${acc}`
}
function loadHidden(acc: string): boolean {
  try {
    return localStorage.getItem(hideKey(acc)) === '1'
  } catch {
    return false
  }
}
function saveHidden(acc: string, hidden: boolean): void {
  try {
    if (hidden) localStorage.setItem(hideKey(acc), '1')
    else localStorage.removeItem(hideKey(acc))
  } catch {
    /* private browsing / storage blocked — the choice just won't stick */
  }
}

/** 0 (safe) -> positive, mid -> warning, high -> negative. For budgets being *used up* (drawdown, daily loss). */
function usedTone(ratio: number): string {
  if (ratio >= 0.8) return 'bg-negative'
  if (ratio >= 0.5) return 'bg-warning'
  return 'bg-positive'
}

function Gauge({ label, ratio, sub, tone }: { label: string; ratio: number; sub: string; tone: string }) {
  const pct = Math.min(100, Math.max(0, ratio * 100))
  return (
    <div>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-secondary">{pct.toFixed(0)}%</span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated">
        <span className={`block h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1 text-[10.5px] text-muted">{sub}</p>
    </div>
  )
}

const DEFAULTS: Omit<ChallengeConfigInput, 'account_id' | 'account_size'> = {
  firm: '5ers',
  phase1_target_pct: 10,
  phase2_target_pct: 5,
  max_drawdown_pct: 10,
  daily_loss_pct: 5,
  min_profit_days: 3,
  profit_day_threshold_pct: 0.5,
  drawdown_mode: 'trailing',
  consistency_pct: 40,
}

/** "2026-10-19" as a short local date; built from its parts so it never shifts a day. */
function shortDay(iso: string | null): string {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, (m ?? 1) - 1, d ?? 1).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/**
 * The consistency rule as a meter: how much of the profit one day made, against the firm's limit.
 * The bar is "your best day as a share of your profit" (0-100%); the tick is the firm's limit, so
 * the fill staying left of the tick is a pass.
 */
function ConsistencyMeter({ s, onSetLimit }: { s: ChallengeStatus; onSetLimit: () => void }) {
  const status = s.consistency_status
  const share = s.consistency_best_day_pct
  const limit = s.consistency_limit_pct
  const fill = Math.min(100, Math.max(0, share ?? 0))
  const fail = status === 'fail'
  const verdict =
    status === 'pass' ? { text: 'Would pass', tone: 'border-positive/30 bg-positive/10 text-positive' }
    : fail ? { text: 'Would fail', tone: 'border-negative/30 bg-negative/10 text-negative' }
    : status === 'no_profit' ? { text: 'No profit yet', tone: 'border-border bg-surface-elevated text-muted' }
    : { text: 'No limit set', tone: 'border-border bg-surface-elevated text-muted' }

  let line: ReactNode
  if (status === 'no_profit') {
    line = 'The rule compares your best day with your total profit, so it starts once you are net up this phase.'
  } else if (share == null) {
    line = 'No winning day yet.'
  } else {
    line = (
      <>
        Best day {money(s.consistency_best_day_amount)} ({shortDay(s.consistency_best_day_date)}) is {share.toFixed(1)}% of your{' '}
        {money(s.consistency_total_profit)} profit since {shortDay(s.config?.phase_start_date ?? null)}
        {limit != null ? <> · limit {limit}%</> : null}.
      </>
    )
  }

  return (
    <div className="sm:col-span-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <span className="text-muted">Consistency rule (best day vs total profit)</span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${verdict.tone}`}>{verdict.text}</span>
      </div>
      <div className="relative mt-1.5 h-2 w-full rounded-full bg-surface-elevated">
        <span
          className={`block h-full rounded-full ${status === 'pass' ? 'bg-positive' : fail ? 'bg-negative' : 'bg-secondary/50'}`}
          style={{ width: `${fill}%` }}
        />
        {limit != null ? (
          <span
            className="absolute -top-1 h-4 w-0.5 rounded bg-primary"
            style={{ left: `calc(${Math.min(100, limit)}% - 1px)` }}
            title={`Your firm's limit: ${limit}%`}
          />
        ) : null}
      </div>
      <p className="mt-1 text-[10.5px] text-muted">{line}</p>
      {fail && s.consistency_extra_needed != null ? (
        <p className="mt-0.5 text-[10.5px] text-secondary">
          To pass you need about {money(s.consistency_extra_needed)} more profit from other days, without a new day bigger than{' '}
          {money(s.consistency_best_day_amount)}.
        </p>
      ) : null}
      {status === 'pass' && s.consistency_next_day_max != null ? (
        <p className="mt-0.5 text-[10.5px] text-secondary">
          Your next day can make up to {money(s.consistency_next_day_max)} and you would still pass.
        </p>
      ) : null}
      {status === 'off' ? (
        <p className="mt-0.5 text-[10.5px] text-muted">
          Many prop firms cap how much of your profit one day can make.{' '}
          <button type="button" onClick={onSetLimit} className="text-accent hover:underline">
            Set your firm's limit
          </button>{' '}
          to see if you would pass.
        </p>
      ) : null}
    </div>
  )
}

function SetupForm({
  accountId,
  existing,
  firstTradeDate,
  onSaved,
  onCancel,
}: {
  accountId: string
  existing: ChallengeConfig | null
  firstTradeDate: string | null
  onSaved: (s: ChallengeStatus) => void
  onCancel?: () => void
}) {
  const [form, setForm] = useState({
    firm: existing?.firm ?? DEFAULTS.firm ?? '5ers',
    account_size: existing?.account_size ?? 5000,
    phase1_target_pct: existing?.phase1_target_pct ?? DEFAULTS.phase1_target_pct ?? 10,
    phase2_target_pct: existing?.phase2_target_pct ?? DEFAULTS.phase2_target_pct ?? 5,
    max_drawdown_pct: existing?.max_drawdown_pct ?? DEFAULTS.max_drawdown_pct ?? 10,
    daily_loss_pct: existing?.daily_loss_pct ?? DEFAULTS.daily_loss_pct ?? 5,
    min_profit_days: existing?.min_profit_days ?? DEFAULTS.min_profit_days ?? 3,
    profit_day_threshold_pct: existing?.profit_day_threshold_pct ?? DEFAULTS.profit_day_threshold_pct ?? 0.5,
    drawdown_mode: existing?.drawdown_mode ?? DEFAULTS.drawdown_mode ?? 'trailing',
    consistency_pct: existing?.consistency_pct ?? DEFAULTS.consistency_pct ?? 40,
  })
  const today = todayIso()
  const savedStart = existing?.phase_start_date ?? today
  const [startDate, setStartDate] = useState(savedStart)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const field = (k: keyof typeof form, label: string, step = '0.1') => (
    <label className="flex flex-col gap-1 text-[11px] text-muted">
      {label}
      <input
        type="number"
        step={step}
        value={form[k] as number}
        onChange={(e) => setForm((f) => ({ ...f, [k]: Number(e.target.value) }))}
        className="tl-input"
      />
    </label>
  )

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      // only send the start when it was changed: sending it again would move the drawdown start too
      const s = await saveChallengeConfig({
        account_id: accountId,
        ...form,
        ...(startDate && startDate !== savedStart ? { start_date: startDate } : {}),
      })
      onSaved(s)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the challenge config.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <label className="col-span-2 flex flex-col gap-1 text-[11px] text-muted sm:col-span-1">
          Firm
          <input
            type="text"
            value={form.firm}
            onChange={(e) => setForm((f) => ({ ...f, firm: e.target.value }))}
            className="tl-input"
          />
        </label>
        {field('account_size', 'Account size ($)', '1')}
        {field('phase1_target_pct', 'Phase 1 target (%)')}
        {field('phase2_target_pct', 'Phase 2 target (%)')}
        {field('max_drawdown_pct', 'Max drawdown (%)')}
        {field('daily_loss_pct', 'Daily loss limit (%)')}
        {field('min_profit_days', 'Min profit days', '1')}
        {field('profit_day_threshold_pct', 'Profit day threshold (%)')}
        {field('consistency_pct', 'Consistency: best day max (% of profit, 0 = none)', '1')}
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Drawdown mode
          <select
            value={form.drawdown_mode}
            onChange={(e) => setForm((f) => ({ ...f, drawdown_mode: e.target.value as 'trailing' | 'static' }))}
            className="tl-select"
          >
            <option value="trailing">Trailing (from peak)</option>
            <option value="static">Static (from initial size)</option>
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Count my trades from
          <input
            type="date"
            value={startDate}
            max={today}
            onChange={(e) => setStartDate(e.target.value)}
            className="tl-input"
          />
        </label>
        {firstTradeDate && startDate !== firstTradeDate ? (
          <button type="button" onClick={() => setStartDate(firstTradeDate)} className="pb-2 text-[11px] text-accent hover:underline">
            Use my first trade on this account ({shortDay(firstTradeDate)})
          </button>
        ) : null}
        <p className="basis-full text-[10.5px] text-muted">
          Set this to the day your funded account started. Only trades from that day on count towards profit days,
          the consistency meter and the drawdown.
        </p>
      </div>
      <p className="text-[10.5px] text-muted">
        Drawdown mode isn't confirmed against your firm's own methodology — trailing is the more conservative
        assumption. Check your firm's dashboard if this ever gets close to mattering.
      </p>
      <p className="text-[10.5px] text-muted">
        Consistency rule: some firms say your best day may be at most a set share of your total profit (for example
        40%). Type your firm's number from their rules page; leave 0 if they have no such rule.
      </p>
      {error ? <p className="text-xs text-negative">{error}</p> : null}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || form.account_size <= 0}
          className="rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
          style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
        >
          {busy ? 'Saving…' : existing ? 'Save changes' : 'Start tracking'}
        </button>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-border px-3 py-1.5 text-xs text-secondary hover:bg-surface-hover"
          >
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  )
}

/**
 * Challenge Tracker — phase progress, drawdown budget, daily-loss budget and
 * profit-day counter against a per-account prop-firm rule set (5ers-shaped
 * defaults, fully editable). Pure display + a settings blob; no execution path.
 */
export function ChallengeTracker({ account }: { account?: string }) {
  const [status, setStatus] = useState<ChallengeStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(false)
  const [busyAction, setBusyAction] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [hidden, setHidden] = useState(false)

  const acc = account && account.toUpperCase() !== 'ALL' ? account : undefined

  useEffect(() => {
    setHidden(acc ? loadHidden(acc) : false)
  }, [acc])

  useEffect(() => {
    if (!acc) {
      setStatus(null)
      return
    }
    const c = new AbortController()
    setLoading(true)
    getChallengeStatus(acc, c.signal)
      .then((s) => {
        if (!c.signal.aborted) setStatus(s)
      })
      .catch(() => {
        if (!c.signal.aborted) setStatus(null)
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false)
      })
    return () => c.abort()
  }, [acc])

  if (!acc) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 text-xs text-muted">
        Select one account above (not "All accounts") to track it against a prop-firm challenge.
      </div>
    )
  }

  if (loading && !status) {
    return <div className="rounded-xl border border-border bg-surface p-4 text-xs text-muted">Loading challenge…</div>
  }

  async function advance(to: '2' | 'funded') {
    if (!acc) return
    setBusyAction(true)
    setActionError(null)
    try {
      setStatus(await advanceChallengePhase(acc, to))
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not advance the phase.')
    } finally {
      setBusyAction(false)
    }
  }

  async function doReset() {
    if (!acc || !confirm(`Restart the ${describeAccount(acc).label} challenge from Phase 1 at the configured account size?`)) return
    setBusyAction(true)
    setActionError(null)
    try {
      setStatus(await resetChallenge(acc))
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not reset the challenge.')
    } finally {
      setBusyAction(false)
    }
  }

  async function doRemove() {
    if (!acc || !confirm(`Stop tracking a challenge for ${describeAccount(acc).label}? This only removes the tracker, not any trades.`)) return
    setBusyAction(true)
    setActionError(null)
    try {
      await deleteChallengeConfig(acc)
      setStatus(await getChallengeStatus(acc))
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not remove the tracker.')
    } finally {
      setBusyAction(false)
    }
  }

  if (!status?.configured && hidden && !editing) {
    return (
      <div className="flex items-center justify-between rounded-xl border border-border-subtle bg-surface/50 p-3 text-[11px] text-muted">
        <span>Not tracking a prop-firm challenge on {describeAccount(acc).label}.</span>
        <button
          type="button"
          onClick={() => {
            setHidden(false)
            saveHidden(acc, false)
          }}
          className="text-accent hover:underline"
        >
          Track one instead?
        </button>
      </div>
    )
  }

  if (!status?.configured || editing) {
    return (
      <SectionCard
        title={status?.configured ? 'Edit challenge rules' : 'Set up challenge tracking'}
        action={
          !status?.configured && !editing ? (
            <button
              type="button"
              onClick={() => {
                setHidden(true)
                saveHidden(acc, true)
              }}
              className="tl-btn tl-btn--ghost tl-btn--sm"
            >
              Not a challenge account? Hide
            </button>
          ) : undefined
        }
      >
        <p className="text-[11px] text-muted">
          {status?.configured
            ? "Editing keeps your current phase and progress — this only changes the rules."
            : `Track ${describeAccount(acc).label} against a prop-firm evaluation's phase target, drawdown budget, daily-loss budget and minimum profit days.`}
        </p>
        <div className="mt-3">
          <SetupForm
            accountId={acc}
            existing={status?.config ?? null}
            firstTradeDate={status?.first_trade_date ?? null}
            onSaved={(s) => {
              setStatus(s)
              setEditing(false)
            }}
            onCancel={status?.configured ? () => setEditing(false) : undefined}
          />
        </div>
      </SectionCard>
    )
  }

  const s = status
  const phaseLabel = s.phase === 'funded' ? 'Funded' : `Phase ${s.phase}`
  const profitDaysDone = (s.profit_days_count ?? 0) >= (s.min_profit_days ?? 0)

  const headerAction = (
    <div className="flex items-center gap-2">
      <span
        className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
          s.phase === 'funded'
            ? 'border-positive/30 bg-positive/10 text-positive'
            : 'border-accent/30 bg-accent/10 text-accent'
        }`}
      >
        {phaseLabel}
      </span>
      <div className="flex gap-1.5 text-[11px]">
        <button type="button" onClick={() => setEditing(true)} className="text-muted hover:text-primary">
          Edit
        </button>
        <span className="text-border">·</span>
        <button type="button" onClick={doReset} disabled={busyAction} className="text-muted hover:text-warning">
          Reset
        </button>
        <span className="text-border">·</span>
        <button type="button" onClick={doRemove} disabled={busyAction} className="text-muted hover:text-negative">
          Remove
        </button>
      </div>
    </div>
  )

  return (
    <SectionCard title={`${s.config?.firm} challenge`} action={headerAction}>
      <DisclaimerNote />
      {actionError ? <p className="mb-2 text-xs text-negative">{actionError}</p> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {/* phase progress */}
        <div>
          {s.phase === 'funded' ? (
            <div className="rounded-lg border border-positive/30 bg-positive/10 p-3">
              <p className="text-xs font-semibold text-positive">Funded — {money(s.current_balance)}</p>
              <p className="mt-0.5 text-[11px] text-secondary">
                +{money(s.phase_gain_amount)} since funding. Check your firm's dashboard for the payout cycle.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-muted">Phase {s.phase} progress</span>
                <span className="font-mono text-secondary">
                  {money(s.phase_gain_amount)} / {money(s.phase_target_amount)}
                </span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-surface-elevated">
                <span
                  className="block h-full rounded-full"
                  style={{ width: `${Math.min(100, (s.phase_progress_ratio ?? 0) * 100)}%`, background: 'var(--tl-gradient-primary)' }}
                />
              </div>
              <p className="mt-1 text-[10.5px] text-muted">
                {s.phase_progress_pct?.toFixed(2)}% of {s.phase_target_pct}% target · balance {money(s.current_balance)}
              </p>
            </>
          )}
        </div>

        {/* profit days */}
        <div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-muted">Profit days this phase</span>
            <span className={`font-mono ${profitDaysDone ? 'text-positive' : 'text-secondary'}`}>
              {s.profit_days_count} / {s.min_profit_days}
            </span>
          </div>
          <div className="mt-1 flex gap-1">
            {Array.from({ length: s.min_profit_days ?? 0 }).map((_, i) => (
              <span
                key={i}
                className={`h-1.5 flex-1 rounded-full ${i < (s.profit_days_count ?? 0) ? 'bg-positive' : 'bg-surface-elevated'}`}
              />
            ))}
          </div>
          <p className="mt-1 text-[10.5px] text-muted">
            &ge;{s.config?.profit_day_threshold_pct}% of account size per day
          </p>
        </div>

        {s.phase !== 'funded' ? (
          <>
            <Gauge
              label={`Drawdown budget (${s.drawdown_mode})`}
              ratio={s.drawdown_budget_used_ratio ?? 0}
              tone={usedTone(s.drawdown_budget_used_ratio ?? 0)}
              sub={`${s.drawdown_used_pct?.toFixed(2)}% used of ${s.config?.max_drawdown_pct}% · floor ${money(s.drawdown_floor_balance)} · peak ${money(s.peak_balance)}`}
            />
            <Gauge
              label="Daily-loss budget (today)"
              ratio={s.daily_loss_budget_used_ratio ?? 0}
              tone={usedTone(s.daily_loss_budget_used_ratio ?? 0)}
              sub={`${money(s.daily_loss_today_amount)} today · ${s.daily_loss_used_pct?.toFixed(2)}% of ${s.config?.daily_loss_pct}% limit`}
            />
          </>
        ) : null}

        <ConsistencyMeter s={s} onSetLimit={() => setEditing(true)} />
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle pt-2.5">
        {s.phase === '1' ? (
          <button
            type="button"
            onClick={() => advance('2')}
            disabled={busyAction}
            className="rounded-lg border border-accent/40 bg-accent/10 px-2.5 py-1 text-[11px] font-medium text-accent hover:bg-accent/20 disabled:opacity-50"
          >
            Mark Phase 1 passed &rarr; Phase 2
          </button>
        ) : s.phase === '2' ? (
          <button
            type="button"
            onClick={() => advance('funded')}
            disabled={busyAction}
            className="rounded-lg border border-positive/40 bg-positive/10 px-2.5 py-1 text-[11px] font-medium text-positive hover:bg-positive/20 disabled:opacity-50"
          >
            Mark Phase 2 passed &rarr; Funded
          </button>
        ) : (
          <span />
        )}
        <p className="text-[10px] text-muted">{s.disclaimer}</p>
      </div>
    </SectionCard>
  )
}
