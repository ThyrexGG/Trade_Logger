import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '../intelligence/primitives'
import { SaveToJournal } from './SaveToJournal'
import { getJournal } from '../../api/operations'
import { getChallengeStatus } from '../../api/challenge'
import type { ChallengeStatus } from '../../types/challenge'

const ACCOUNT_KEY = 'tl.pretrade.account'

const SETUP_PRESETS = [
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

export interface ChecklistPrefill {
  /** Bumped every time a new prefill should be applied, even if the field
   * values happen to match the previous prefill (e.g. two candidates with
   * the same level) — a plain useEffect keyed on the values wouldn't re-fire. */
  version: number
  symbol?: string
  direction?: 'long' | 'short'
  entry?: number
  stopLoss?: number
  note?: string
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
    return lines.join('\n')
  }

  const ready = symbol.trim().length > 0 && thesis.trim().length > 0

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
          <label className="col-span-2 flex flex-col gap-1 text-[11px] text-muted">
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

        <label className="mt-3 flex flex-col gap-1 text-[11px] text-muted">
          Thesis — why this trade, in your own words
          <textarea
            value={thesis}
            onChange={(e) => {
              setThesis(e.target.value)
              invalidate()
            }}
            rows={3}
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

        <button
          type="button"
          onClick={() => setSnapshot(buildDescription())}
          disabled={!ready}
          className="mt-3 w-full rounded-lg px-3 py-2 text-xs font-semibold disabled:opacity-40"
          style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
        >
          Build plan
        </button>
        {!ready ? <p className="mt-1 text-[10px] text-muted">Symbol and a thesis are required.</p> : null}

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
