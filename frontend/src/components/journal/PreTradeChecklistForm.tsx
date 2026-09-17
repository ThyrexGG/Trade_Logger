import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '../intelligence/primitives'
import { SaveToJournal } from './SaveToJournal'
import { getJournal } from '../../api/operations'
import { getChallengeStatus } from '../../api/challenge'
import type { ChallengeStatus } from '../../types/challenge'

const ACCOUNT_KEY = 'tl.pretrade.account'

// Exported so ManualTradeForm (logging a trade after the fact) offers the
// same setup vocabulary as planning one before the fact — one tag taxonomy.
export const SETUP_PRESETS = [
  'BREAKOUT',
  'SUPPORT / RESISTANCE BOUNCE',
  'ORDER BLOCK / FVG',
  'NEWS SCALP',
  'TREND FOLLOWING',
  'MEAN REVERSION',
  'LIQUIDITY GRAB',
  'SUPPLY & DEMAND',
  'CHART PATTERN',
  'CUSTOM SETUP',
]

interface ChecklistItem {
  id: string
  label: string
}

const CHECKLIST: ChecklistItem[] = [
  { id: 'defined_setup', label: 'This matches a setup I can clearly define — not "it just looks right"' },
  { id: 'good_rr', label: 'Reward-to-risk is at least 1:2' },
  { id: 'known_invalidation', label: "I know exactly where I'm wrong (a real stop, not \"I'll move it if needed\")" },
  { id: 'within_risk_budget', label: "This doesn't put me close to today's daily-loss limit" },
  { id: 'not_emotional', label: "I'm not entering from FOMO or revenge after a loss" },
  { id: 'comfortable_public', label: "I'd be equally comfortable posting this entry publicly right now" },
]

function ratioTone(ratio: number): string {
  if (ratio >= 0.8) return 'text-negative'
  if (ratio >= 0.5) return 'text-warning'
  return 'text-positive'
}

/** How much of what's LEFT of today's daily-loss budget this one trade's
 * planned risk would use up, if the stop is hit. Distinct from the
 * account-wide ratios above: those describe trades already closed today,
 * this describes a trade that hasn't happened yet. Null when there isn't
 * enough configured/entered to compute it (no challenge, or no risk amount
 * typed in) — callers show nothing rather than a misleading 0%. */
function riskAgainstRemainingBudget(
  challenge: ChallengeStatus | null,
  riskAmount: number | null,
): { ratio: number; remainingBudget: number } | null {
  if (!challenge?.configured || !challenge.config || riskAmount === null || riskAmount <= 0) return null
  const totalDailyBudget = (challenge.config.daily_loss_pct / 100) * challenge.config.account_size
  const usedToday = challenge.daily_loss_today_amount ?? 0
  const remainingBudget = totalDailyBudget - usedToday
  if (remainingBudget <= 0) return { ratio: Infinity, remainingBudget }
  return { ratio: riskAmount / remainingBudget, remainingBudget }
}

function tradeRiskTone(ratio: number): string {
  if (ratio >= 0.6) return 'text-negative'
  if (ratio >= 0.3) return 'text-warning'
  return 'text-positive'
}

function biasTone(bias: string): string {
  if (bias === 'bullish') return 'text-positive'
  if (bias === 'bearish') return 'text-negative'
  return 'text-muted'
}

export interface ChecklistPrefill {
  /** Bumped every time a new prefill should be applied, even if the field
   * values happen to match the previous prefill (e.g. two candidates with
   * the same level) — a plain useEffect keyed on the values wouldn't re-fire. */
  version: number
  symbol?: string
  direction?: 'long' | 'short'
  entry?: number
  stopLoss?: number
  takeProfit?: number
  note?: string
  /** Read-only context carried over from the Killzone Scanner — shown as
   * reference underneath the plan fields, not mirrored into any editable
   * form state (there's nothing to edit; it's what the scan actually saw). */
  htfBias?: 'bullish' | 'bearish' | 'neutral'
  htfTrend?: string
  keyLevel?: { label: string; price: number }
}

/**
 * Pre-trade plan + honesty checklist. Fill this out *before* entering — a
 * timestamped record of what was actually planned, so a later review is
 * honest instead of hindsight-shaped. Saves to the Journal (kind "plan") or
 * attaches straight to a trade if one's already synced. Not a gate: nothing
 * here blocks saving regardless of what's checked.
 *
 * Accepts an optional `prefill` (from a Killzone Scanner candidate) to seed
 * symbol/direction/entry/stop — still fully editable before saving.
 */
export function PreTradeChecklistForm({ prefill }: { prefill?: ChecklistPrefill }) {
  const [accounts, setAccounts] = useState<string[]>([])
  const [account, setAccount] = useState<string>(() => {
    try {
      return localStorage.getItem(ACCOUNT_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [challenge, setChallenge] = useState<ChallengeStatus | null>(null)

  const [symbol, setSymbol] = useState('')
  const [direction, setDirection] = useState<'long' | 'short'>('long')
  const [setupTag, setSetupTag] = useState(SETUP_PRESETS[0])
  const [entry, setEntry] = useState('')
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')
  const [riskAmount, setRiskAmount] = useState('')
  const [riskAck, setRiskAck] = useState(false)
  const [thesis, setThesis] = useState('')
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [snapshot, setSnapshot] = useState<string | null>(null)

  useEffect(() => {
    getJournal()
      .then((r) => {
        setAccounts(r.accounts)
        if (!account && r.accounts.length) setAccount(r.accounts[0])
      })
      .catch(() => setAccounts([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!account) {
      setChallenge(null)
      return
    }
    try {
      localStorage.setItem(ACCOUNT_KEY, account)
    } catch {
      /* private browsing / storage blocked */
    }
    const c = new AbortController()
    getChallengeStatus(account, c.signal)
      .then((s) => setChallenge(s))
      .catch(() => setChallenge(null))
    return () => c.abort()
  }, [account])

  // apply a scanner candidate's fields when a new prefill arrives
  useEffect(() => {
    if (!prefill) return
    if (prefill.symbol) setSymbol(prefill.symbol.toUpperCase())
    if (prefill.direction) setDirection(prefill.direction)
    if (prefill.entry !== undefined) setEntry(String(prefill.entry))
    if (prefill.stopLoss !== undefined) setStopLoss(String(prefill.stopLoss))
    if (prefill.takeProfit !== undefined) setTakeProfit(String(prefill.takeProfit))
    if (prefill.note) setThesis((t) => (t ? t : prefill.note!))
    setSnapshot(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill?.version])

  const rr = useMemo(() => {
    const e = parseFloat(entry)
    const sl = parseFloat(stopLoss)
    const tp = parseFloat(takeProfit)
    if (!isFinite(e) || !isFinite(sl) || !isFinite(tp)) return null
    const risk = Math.abs(e - sl)
    const reward = Math.abs(tp - e)
    return risk > 0 ? reward / risk : null
  }, [entry, stopLoss, takeProfit])

  const tradeRisk = useMemo(() => {
    const amt = parseFloat(riskAmount)
    return riskAgainstRemainingBudget(challenge, isFinite(amt) && amt > 0 ? amt : null)
  }, [challenge, riskAmount])

  // Only the red zone asks for an extra click, and only once an amount is
  // actually entered -- an empty field shouldn't silently block saving.
  const needsRiskAck = tradeRisk !== null && tradeRisk.ratio >= 0.6
  useEffect(() => {
    if (!needsRiskAck) setRiskAck(false)
  }, [needsRiskAck])

  const checkedCount = CHECKLIST.filter((c) => checked[c.id]).length

  function invalidate() {
    setSnapshot(null)
  }

  function buildDescription(): string {
    const lines: string[] = []
    lines.push(`Pre-trade plan: ${direction.toUpperCase()} ${symbol.toUpperCase()} — ${setupTag}`)
    const levels: string[] = []
    if (entry) levels.push(`Entry ${entry}`)
    if (stopLoss) levels.push(`SL ${stopLoss}`)
    if (takeProfit) levels.push(`TP ${takeProfit}`)
    if (rr !== null) levels.push(`R:R ${rr.toFixed(2)}`)
    if (levels.length) lines.push(levels.join(' · '))
    lines.push('')
    lines.push(`Thesis: ${thesis.trim() || '(none written)'}`)
    lines.push('')
    lines.push(`Checklist (${checkedCount}/${CHECKLIST.length}):`)
    for (const c of CHECKLIST) {
      lines.push(`${checked[c.id] ? '✓' : '✗'} ${c.label}`)
    }
    if (challenge?.configured) {
      lines.push('')
      lines.push(
        `Account budgets at the time: drawdown ${((challenge.drawdown_budget_used_ratio ?? 0) * 100).toFixed(0)}% used, ` +
          `daily loss ${((challenge.daily_loss_budget_used_ratio ?? 0) * 100).toFixed(0)}% used.`,
      )
    }
    if (tradeRisk) {
      lines.push(
        `Planned risk: $${parseFloat(riskAmount).toFixed(0)} (` +
          `${tradeRisk.ratio === Infinity ? '>100' : (tradeRisk.ratio * 100).toFixed(0)}% of the daily-loss budget remaining at plan time)` +
          (needsRiskAck ? ' — acknowledged and taken anyway.' : '.'),
      )
    }
    return lines.join('\n')
  }

  const ready = symbol.trim().length > 0 && thesis.trim().length > 0 && (!needsRiskAck || riskAck)

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SectionCard title="The plan">
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Account
            <select
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            >
              {accounts.length === 0 ? <option value="">No synced accounts</option> : null}
              {accounts.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Symbol
            <input
              type="text"
              value={symbol}
              onChange={(e) => {
                setSymbol(e.target.value.toUpperCase())
                invalidate()
              }}
              placeholder="EURUSD"
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Direction
            <select
              value={direction}
              onChange={(e) => {
                setDirection(e.target.value as 'long' | 'short')
                invalidate()
              }}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            >
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Setup
            <select
              value={setupTag}
              onChange={(e) => {
                setSetupTag(e.target.value)
                invalidate()
              }}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            >
              {SETUP_PRESETS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Entry
            <input
              type="number"
              step="any"
              value={entry}
              onChange={(e) => {
                setEntry(e.target.value)
                invalidate()
              }}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Stop loss
            <input
              type="number"
              step="any"
              value={stopLoss}
              onChange={(e) => {
                setStopLoss(e.target.value)
                invalidate()
              }}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Take profit
            <input
              type="number"
              step="any"
              value={takeProfit}
              onChange={(e) => {
                setTakeProfit(e.target.value)
                invalidate()
              }}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Risk amount ($) if stopped out
            <input
              type="number"
              step="any"
              min="0"
              value={riskAmount}
              onChange={(e) => {
                setRiskAmount(e.target.value)
                invalidate()
              }}
              placeholder="e.g. 50"
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            />
          </label>
        </div>

        {rr !== null ? (
          <p className="mt-2 text-[11px] text-secondary">
            Reward-to-risk: <span className="font-mono font-semibold text-primary">{rr.toFixed(2)}</span>
          </p>
        ) : null}

        {challenge?.configured ? (
          <div className="mt-3 rounded-lg border border-border-subtle bg-surface-elevated/40 p-2.5 text-[11px]">
            <p className="text-muted">Live budgets on {account} right now:</p>
            <p className="mt-1">
              Drawdown{' '}
              <span className={`font-mono font-semibold ${ratioTone(challenge.drawdown_budget_used_ratio ?? 0)}`}>
                {((challenge.drawdown_budget_used_ratio ?? 0) * 100).toFixed(0)}%
              </span>{' '}
              used · Daily loss{' '}
              <span className={`font-mono font-semibold ${ratioTone(challenge.daily_loss_budget_used_ratio ?? 0)}`}>
                {((challenge.daily_loss_budget_used_ratio ?? 0) * 100).toFixed(0)}%
              </span>{' '}
              used
            </p>
          </div>
        ) : null}

        {tradeRisk ? (
          <div
            className="mt-3 rounded-lg border p-2.5 text-[11px]"
            style={
              tradeRisk.ratio >= 0.6
                ? { borderColor: 'var(--tl-negative, #b3392f)', background: 'color-mix(in srgb, var(--tl-negative, #b3392f) 10%, transparent)' }
                : undefined
            }
          >
            <p className="text-muted">This trade, if the stop is hit:</p>
            <p className="mt-1">
              Risks{' '}
              <span className="font-mono font-semibold text-primary">${parseFloat(riskAmount).toFixed(0)}</span> —{' '}
              <span className={`font-mono font-semibold ${tradeRiskTone(tradeRisk.ratio)}`}>
                {tradeRisk.ratio === Infinity ? '∞' : `${(tradeRisk.ratio * 100).toFixed(0)}%`}
              </span>{' '}
              of the ${Math.max(0, tradeRisk.remainingBudget).toFixed(0)} left in today's daily-loss budget
            </p>
            {tradeRisk.ratio >= 0.6 ? (
              <p className="mt-1.5 font-medium text-negative">
                {tradeRisk.remainingBudget <= 0
                  ? "Today's daily-loss budget is already used up. A loss here likely breaches it."
                  : "If this loses, you're at or near today's daily-loss limit. Worth asking whether this is the trade, or the day, talking."}
              </p>
            ) : null}
          </div>
        ) : null}

        {prefill?.htfBias || prefill?.keyLevel ? (
          <div className="mt-3 rounded-lg border border-border-subtle bg-surface-elevated/40 p-2.5 text-[11px]">
            <p className="text-muted">From the Killzone Scanner, at the time this was planned:</p>
            {prefill.htfBias ? (
              <p className="mt-1">
                HTF bias{' '}
                <span className={`font-semibold uppercase ${biasTone(prefill.htfBias)}`}>{prefill.htfBias}</span>
                {prefill.htfTrend ? <span className="text-muted"> — {prefill.htfTrend}</span> : null}
              </p>
            ) : null}
            {prefill.keyLevel ? (
              <p className="mt-1">
                Key level to watch:{' '}
                <span className="font-mono font-semibold text-primary">{prefill.keyLevel.price}</span>{' '}
                <span className="text-muted">({prefill.keyLevel.label})</span>
              </p>
            ) : null}
          </div>
        ) : null}

        <label className="mt-3 flex flex-col gap-1 text-[11px] text-muted">
          Thesis — why this trade, in your own words
          <textarea
            value={thesis}
            onChange={(e) => {
              setThesis(e.target.value)
              invalidate()
            }}
            rows={7}
            placeholder="What are you actually seeing, and why does it justify risking money?"
            className="resize-y rounded border border-border bg-background px-2 py-1.5 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
      </SectionCard>

      <SectionCard title="Checklist" info="Not a gate — nothing here stops you from trading. It's a mirror: an honest record of what you actually checked before this entry, to compare against later.">
        <div className="space-y-2">
          {CHECKLIST.map((c) => (
            <label
              key={c.id}
              className="flex cursor-pointer items-start gap-2 rounded-lg border border-border-subtle bg-surface-elevated/30 p-2.5 text-xs text-secondary hover:bg-surface-hover"
            >
              <input
                type="checkbox"
                checked={Boolean(checked[c.id])}
                onChange={(e) => {
                  setChecked((prev) => ({ ...prev, [c.id]: e.target.checked }))
                  invalidate()
                }}
                className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-accent"
              />
              {c.label}
            </label>
          ))}
        </div>
        <p className="mt-2 text-[11px] text-muted">{checkedCount} / {CHECKLIST.length} checked</p>

        {needsRiskAck ? (
          <label className="mt-3 flex cursor-pointer items-start gap-2 rounded-lg border border-negative/40 bg-negative/10 p-2.5 text-xs text-primary">
            <input
              type="checkbox"
              checked={riskAck}
              onChange={(e) => setRiskAck(e.target.checked)}
              className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-negative"
            />
            I see the daily-loss warning above and want to take this trade anyway.
          </label>
        ) : null}

        <button
          type="button"
          onClick={() => setSnapshot(buildDescription())}
          disabled={!ready}
          className="mt-3 w-full rounded-lg px-3 py-2 text-xs font-semibold disabled:opacity-40"
          style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
        >
          Build plan
        </button>
        {!ready ? (
          <p className="mt-1 text-[10px] text-muted">
            {symbol.trim().length === 0 || thesis.trim().length === 0
              ? 'Symbol and a thesis are required.'
              : 'Acknowledge the daily-loss warning above to continue.'}
          </p>
        ) : null}

        {snapshot ? (
          <SaveToJournal
            description={snapshot}
            defaultKind="plan"
            defaultInstrument={symbol}
            defaultTitle={`${direction.toUpperCase()} ${symbol} plan`}
          />
        ) : null}
      </SectionCard>
    </div>
  )
}
