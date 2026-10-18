import { useState, type ReactNode } from 'react'
import type { DirectionStats } from '../../types/analytics'
import { SectionCard } from '../research/primitives'
import { formatUsd } from '../../lib/format'
import { RadarChart } from './RadarChart'

/**
 * The lower half of Analytics, laid out so no card sits beside a much taller
 * one: each card is a full-width row that balances itself inside (two
 * columns of winners / losers; radar beside its scores).
 */

function signedUsd(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v)}`
}

function toneText(v: number): string {
  return v > 0 ? 'text-positive' : v < 0 ? 'text-negative' : 'text-secondary'
}

// ---------------------------------------------------------------------------
// Where you make and lose money

export interface MoneyRow {
  label: string
  net: number
  trades: number
  /** 0–100, optional */
  winRate?: number
}

const COLLAPSED = 8

function MoneyColumn({
  title,
  rows,
  max,
  tone,
  showAll,
  empty,
}: {
  title: string
  rows: MoneyRow[]
  max: number
  tone: 'pos' | 'neg'
  showAll: boolean
  empty: string
}) {
  const total = rows.reduce((s, r) => s + r.net, 0)
  const shown = showAll ? rows : rows.slice(0, COLLAPSED)
  return (
    <div className="min-w-0">
      <div className="mb-1.5 flex items-baseline justify-between gap-2 border-b border-border-subtle pb-1.5">
        <span className="tl-label">
          {title} · {rows.length}
        </span>
        {rows.length ? <span className={`tl-figure text-xs ${toneText(total)}`}>{signedUsd(total)}</span> : null}
      </div>
      {rows.length === 0 ? (
        <p className="py-2 text-xs text-muted">{empty}</p>
      ) : (
        <ul>
          {shown.map((r) => (
            <li key={r.label} className="flex items-center gap-3 py-[5px] text-[11px]">
              <span className="w-20 shrink-0 truncate font-mono text-secondary" title={r.label}>
                {r.label}
              </span>
              <span className="relative h-1.5 flex-1 rounded-full bg-surface-elevated" aria-hidden="true">
                <span
                  className={`absolute inset-y-0 left-0 rounded-full ${tone === 'pos' ? 'bg-positive' : 'bg-negative'}`}
                  style={{ width: `${Math.max(2, (Math.abs(r.net) / max) * 100)}%` }}
                />
              </span>
              <span className={`w-20 shrink-0 text-right font-mono tabular-nums ${toneText(r.net)}`}>{signedUsd(r.net)}</span>
              <span className="w-16 shrink-0 text-right font-mono text-muted">
                {r.trades}t{r.winRate != null ? ` ${Math.round(r.winRate)}%` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function MoneySplitCard({
  title,
  info,
  rows,
  noun,
}: {
  title: string
  info: string
  rows: MoneyRow[]
  /** "market", "tag" — used in the summary sentence */
  noun: string
}) {
  const [showAll, setShowAll] = useState(false)
  const winners = rows.filter((r) => r.net > 0).sort((a, b) => b.net - a.net)
  const losers = rows.filter((r) => r.net <= 0).sort((a, b) => a.net - b.net)
  const max = Math.max(1e-9, ...rows.map((r) => Math.abs(r.net)))
  const hidden = Math.max(0, winners.length - COLLAPSED) + Math.max(0, losers.length - COLLAPSED)

  let headline: ReactNode = null
  const best = winners[0]
  const worst = losers.find((r) => r.net < 0)
  if (best && worst) {
    headline = (
      <>
        <span className="font-medium">{best.label}</span> makes you the most (<span className={`tl-figure ${toneText(best.net)}`}>{signedUsd(best.net)}</span>);{' '}
        <span className="font-medium">{worst.label}</span> costs you the most (<span className={`tl-figure ${toneText(worst.net)}`}>{signedUsd(worst.net)}</span> over{' '}
        {worst.trades} trade{worst.trades === 1 ? '' : 's'}).
      </>
    )
  } else if (best) {
    headline = <>Every {noun} you traded is in profit — <span className="font-medium">{best.label}</span> the most.</>
  } else if (worst) {
    headline = <>No {noun} is in profit yet — <span className="font-medium">{worst.label}</span> costs you the most.</>
  }

  return (
    <SectionCard
      title={title}
      info={info}
      action={
        hidden > 0 ? (
          <button type="button" onClick={() => setShowAll((v) => !v)} className="text-xs font-medium text-accent hover:underline">
            {showAll ? 'Show fewer' : `Show all ${rows.length}`}
          </button>
        ) : null
      }
    >
      <div className="space-y-3">
        {headline ? <p className="text-sm leading-relaxed text-primary">{headline}</p> : null}
        <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
          <MoneyColumn title="Making money" rows={winners} max={max} tone="pos" showAll={showAll} empty={`No ${noun} is in profit yet.`} />
          <MoneyColumn title="Losing money" rows={losers} max={max} tone="neg" showAll={showAll} empty={`Nothing is losing money. Nice.`} />
        </div>
      </div>
    </SectionCard>
  )
}

// ---------------------------------------------------------------------------
// Your trading profile — radar + score bars + long/short

export interface ProfileScore {
  label: string
  v: number
}

function scoreTone(v: number): { text: string; bar: string } {
  if (v >= 60) return { text: 'text-positive', bar: 'bg-positive' }
  if (v <= 40) return { text: 'text-negative', bar: 'bg-negative' }
  return { text: 'text-secondary', bar: 'bg-accent' }
}

function SideCell({ label, s }: { label: string; s: DirectionStats }) {
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className={`tl-figure mt-0.5 text-sm ${toneText(s.pnl)}`}>{signedUsd(s.pnl)}</p>
      <p className="font-mono text-[10px] text-muted">
        {s.trades} trades · {s.win_rate.toFixed(1)}% win
      </p>
    </div>
  )
}

export function TradingProfileCard({ scores, long, short }: { scores: ProfileScore[]; long: DirectionStats; short: DirectionStats }) {
  const strongest = scores.reduce((a, b) => (b.v > a.v ? b : a))
  const weakest = scores.reduce((a, b) => (b.v < a.v ? b : a))
  const sideGap = Math.abs(long.pnl - short.pnl)
  const betterSide = long.pnl >= short.pnl ? 'longs' : 'shorts'

  return (
    <SectionCard
      title="Your trading profile"
      info="Five 0–100 scores made from the numbers above (profitability, win rate, risk / reward, capital protection, consistency), plus how your buys (long) and sells (short) compare. Not a grade — a shape to eyeball. Green 60+, red 40 and under."
    >
      <div className="grid items-center gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)]">
        <div className="text-accent">
          <RadarChart axes={scores.map((s) => ({ label: s.label, value: s.v }))} />
        </div>
        <div className="space-y-4">
          <p className="text-sm leading-relaxed text-primary">
            Strongest: <span className="font-medium">{strongest.label.toLowerCase()}</span> ({strongest.v.toFixed(0)}). Needs the most work:{' '}
            <span className="font-medium">{weakest.label.toLowerCase()}</span> ({weakest.v.toFixed(0)}).
          </p>
          <ul className="space-y-2">
            {scores.map((s) => {
              const t = scoreTone(s.v)
              return (
                <li key={s.label} className="flex items-center gap-3 text-[11px]">
                  <span className="w-32 shrink-0 text-secondary">{s.label}</span>
                  <span className="relative h-1.5 flex-1 rounded-full bg-surface-elevated" aria-hidden="true">
                    <span className={`absolute inset-y-0 left-0 rounded-full ${t.bar}`} style={{ width: `${Math.max(2, s.v)}%` }} />
                  </span>
                  <span className={`tl-figure w-8 shrink-0 text-right ${t.text}`}>{s.v.toFixed(0)}</span>
                </li>
              )
            })}
          </ul>
          <div className="border-t border-border-subtle pt-3">
            <p className="mb-2 text-xs text-secondary">
              Long vs short
              {long.trades && short.trades ? (
                <span className="text-muted">
                  {' '}
                  · your {betterSide} are {formatUsd(sideGap)} better
                </span>
              ) : null}
            </p>
            <div className="grid grid-cols-2 gap-2">
              <SideCell label="Long (buys)" s={long} />
              <SideCell label="Short (sells)" s={short} />
            </div>
          </div>
        </div>
      </div>
    </SectionCard>
  )
}
