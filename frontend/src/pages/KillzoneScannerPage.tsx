import { useCallback, useEffect, useRef, useState } from 'react'
import { PageContainer } from '../components/shell/PageContainer'
import { SectionCard } from '../components/intelligence/primitives'
import { PreTradeChecklistForm, type ChecklistPrefill } from '../components/journal/PreTradeChecklistForm'
import { InfoTip } from '../components/common/InfoTip'
import { scanKillzone } from '../api/scanner'
import type { KillzoneCandidate, KillzoneScanResponse } from '../types/scanner'

const LTF_OPTIONS = ['1m', '5m', '15m', '1h']

/** Presets for the symbol picker. The field stays free-text — the list is a
 *  shortcut, not a whitelist — so any ticker the data feed serves still works.
 *  Metals sit apart from FX because their tick sizes and typical stop
 *  distances are an order of magnitude different, which matters when reading
 *  levels across the two. */
const SYMBOL_GROUPS: { label: string; symbols: string[] }[] = [
  { label: 'Majors', symbols: ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD'] },
  { label: 'Yen crosses', symbols: ['EURJPY', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY', 'NZDJPY'] },
  { label: 'Other crosses', symbols: ['EURGBP', 'EURAUD', 'EURCHF', 'EURCAD', 'GBPAUD', 'GBPCAD', 'GBPCHF', 'AUDNZD', 'AUDCAD'] },
  { label: 'Metals', symbols: ['XAUUSD', 'XAGUSD'] },
]
const REFRESH_MS = 5 * 60 * 1000
const SYMBOL_KEY = 'tl.scanner.symbol'
const LTF_KEY = 'tl.scanner.ltf'

type Tab = 'scan' | 'plan'

function fmtTime(unixSec: number): string {
  return new Date(unixSec * 1000).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function biasTone(bias: string | null): string {
  if (bias === 'bullish') return 'border-positive/30 bg-positive/10 text-positive'
  if (bias === 'bearish') return 'border-negative/30 bg-negative/10 text-negative'
  return 'border-border-subtle bg-surface-elevated text-muted'
}

/** ★★★☆☆-style rendering of the 0-5 confluence score — a count of disclosed
 *  factors met, not a win probability (see killzone_scanner.py's _confluence). */
function stars(score: number): string {
  const n = Math.max(0, Math.min(5, score ?? 0))
  return '★'.repeat(n) + '☆'.repeat(5 - n)
}

function starTone(score: number): string {
  if (score >= 4) return 'text-positive'
  if (score >= 2) return 'text-warning'
  return 'text-muted'
}

/** One-line breakdown for the confluence tooltip — every factor plain and disclosed.
 *  Defensive against a candidate fetched before this field existed (e.g. a
 *  tab left open across a backend update, or an older cached response) —
 *  shows nothing rather than crashing the page. */
function confluenceTooltip(c: KillzoneCandidate): string {
  return (c.confluence_factors ?? []).map((f) => `${f.met ? '✓' : '✗'} ${f.label}`).join('  ·  ')
}

/** Plain-text/Markdown recap of the current scan — for pasting into a journal
 *  entry, a notes app, or anywhere outside TradeLogger. Same numbers already
 *  on screen, just laid out to paste cleanly. */
function buildMarkdown(data: KillzoneScanResponse, ltf: string): string {
  const lines: string[] = []
  lines.push(`# Killzone scan — ${data.symbol}`)
  lines.push('')
  lines.push(`_${new Date(data.timestamp).toLocaleString()} · entry ${ltf} · bias ${data.htf ?? '1h'}_`)
  lines.push('')
  lines.push(`**HTF bias:** ${data.htf_bias ?? 'unknown'}${data.htf_structure?.recent_sequence ? ` — ${data.htf_structure.recent_sequence}` : ''}`)
  if (data.htf_structure?.last_break) lines.push(`- Last break: ${data.htf_structure.last_break}`)
  if (data.htf_structure?.last_swing_high != null) lines.push(`- Last swing high: ${data.htf_structure.last_swing_high}`)
  if (data.htf_structure?.last_swing_low != null) lines.push(`- Last swing low: ${data.htf_structure.last_swing_low}`)
  lines.push('')
  lines.push(`**Current killzone:** ${data.current_killzone ?? 'unknown'}`)
  lines.push('')
  lines.push('**Draw on liquidity:**')
  const bsl = data.htf_liquidity_targets?.bsl ?? []
  const ssl = data.htf_liquidity_targets?.ssl ?? []
  if (bsl.length === 0 && ssl.length === 0) lines.push('- none nearby')
  bsl.forEach((p) => lines.push(`- BSL ${p.price} (${p.distance_from_price} away)`))
  ssl.forEach((p) => lines.push(`- SSL ${p.price} (${p.distance_from_price} away)`))
  lines.push('')
  lines.push(`**Candidate events (${ltf}):**`)
  if (data.candidates.length === 0) {
    lines.push('- none in the recent window')
  } else {
    data.candidates.forEach((c) => {
      const plan = `entry ${c.potential_entry} / stop ${c.potential_stop}${
        c.potential_target != null ? ` / target ${c.potential_target} (R:R ${c.risk_reward})` : ' / no target nearby'
      }`
      lines.push(
        `- ${c.direction.toUpperCase()} — sweep ${c.sweep_level} (${fmtTime(c.sweep_time)}) → shift ${c.shift_level} (${fmtTime(c.shift_time)}), ${c.killzone}, ${c.agrees_with_htf_bias ? 'agrees with' : 'conflicts with'} HTF bias — ${plan} — confluence ${c.confluence_score}/5`,
      )
    })
  }
  lines.push('')
  lines.push('**Unmitigated FVGs:**')
  if (data.recent_unmitigated_fvgs.length === 0) {
    lines.push('- none currently')
  } else {
    data.recent_unmitigated_fvgs.forEach((f) =>
      lines.push(`- ${f.type} ${f.bottom}–${f.top} — confirmed ${fmtTime(f.creation_time)} (${f.age_candles} candles ago)`),
    )
  }
  lines.push('')
  lines.push(`_Pattern-flagging only, not a signal — data source: ${data.ltf_source ?? 'unknown'} / ${data.htf_source ?? 'unknown'}._`)
  return lines.join('\n')
}

/**
 * Killzone Scanner (`/workspace/killzone-scanner`). Two tabs sharing one
 * workflow: Scan flags candidate liquidity-sweep + market-structure-shift
 * events against the higher-timeframe bias and the active ICT killzone;
 * Plan is the pre-trade checklist, seedable straight from a candidate row
 * ("Plan this") so a flagged event turns into a written plan in one click.
 * Pattern-flagging only — never a signal, never a recommendation, no
 * execution path. Every threshold behind a flag is plain and disclosed (see
 * killzone_scanner.py) — this replaces staring at charts, not judgment.
 */
export function KillzoneScannerPage() {
  const [tab, setTab] = useState<Tab>('scan')
  const [symbol, setSymbol] = useState(() => {
    try {
      return localStorage.getItem(SYMBOL_KEY) ?? 'USDJPY'
    } catch {
      return 'USDJPY'
    }
  })
  const [ltf, setLtf] = useState(() => {
    try {
      return localStorage.getItem(LTF_KEY) ?? '15m'
    } catch {
      return '15m'
    }
  })
  const [data, setData] = useState<KillzoneScanResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef(symbol)
  const [prefill, setPrefill] = useState<ChecklistPrefill | undefined>(undefined)
  const prefillVersion = useRef(0)
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)

  const load = useCallback((sym: string, timeframe: string, signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    scanKillzone(sym.trim().toUpperCase(), timeframe, signal)
      .then((r) => {
        if (signal?.aborted) return
        setData(r)
        setFocusedIndex(null)
        if (!r.ok) setError(r.error ?? 'Scan failed.')
      })
      .catch((e) => {
        if (signal?.aborted) return
        setError(e instanceof Error ? e.message : 'Scan failed.')
      })
      .finally(() => {
        if (!signal?.aborted) setLoading(false)
      })
  }, [])

  useEffect(() => {
    const c = new AbortController()
    load(symbol, ltf, c.signal)
    const interval = window.setInterval(() => load(symbol, ltf), REFRESH_MS)
    return () => {
      c.abort()
      window.clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, ltf])

  function submit() {
    const sym = inputRef.current.trim().toUpperCase() || 'USDJPY'
    setSymbol(sym)
    try {
      localStorage.setItem(SYMBOL_KEY, sym)
    } catch {
      /* private browsing / storage blocked */
    }
    load(sym, ltf)
  }

  function changeLtf(tf: string) {
    setLtf(tf)
    try {
      localStorage.setItem(LTF_KEY, tf)
    } catch {
      /* private browsing / storage blocked */
    }
  }

  async function copySummary() {
    if (!data?.ok) return
    const text = buildMarkdown(data, ltf)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard permission denied / unavailable — nothing to fall back to here */
    }
  }

  function planThis(c: KillzoneCandidate) {
    prefillVersion.current += 1
    setPrefill({
      version: prefillVersion.current,
      symbol: data?.symbol ?? symbol,
      direction: c.direction === 'bullish' ? 'long' : 'short',
      entry: c.shift_level,
      stopLoss: c.sweep_level,
      takeProfit: c.potential_target ?? undefined,
      note: `From Killzone Scanner: ${c.direction} sweep+shift in ${c.killzone}, ${c.agrees_with_htf_bias ? 'agreeing with' : 'conflicting with'} the 1h bias. Confluence ${c.confluence_score}/5 (${confluenceTooltip(c)}).`,
      htfBias: data?.htf_bias ?? undefined,
      htfTrend: data?.htf_structure?.recent_sequence || data?.htf_structure?.last_break || undefined,
      keyLevel: c.potential_target != null
        ? {
            label: c.direction === 'bullish' ? 'nearest BSL — draw on liquidity' : 'nearest SSL — draw on liquidity',
            price: c.potential_target,
          }
        : undefined,
    })
    setTab('plan')
  }

  return (
    <PageContainer
      title="Killzone Scanner"
      description="Scan for candidate liquidity-sweep + structure-shift events, then log the plan before you enter. Pattern-flagging only — it replaces staring at charts, not your own judgment on whether a flagged event is actually worth trading."
    >
      <div className="space-y-4">
        <div className="flex w-fit rounded-xl border border-border p-1 text-xs">
          {(['scan', 'plan'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`rounded-lg px-4 py-1.5 font-medium transition-colors ${tab === t ? 'shadow' : 'text-muted'}`}
              style={tab === t ? { background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' } : undefined}
            >
              {t === 'scan' ? 'Scan' : 'Plan'}
            </button>
          ))}
        </div>

        {tab === 'scan' ? (
          <>
            <SectionCard title="Scan">
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1 text-[11px] text-muted">
                  Symbol
                  <select
                    value={SYMBOL_GROUPS.some((g) => g.symbols.includes(symbol)) ? symbol : ''}
                    onChange={(e) => {
                      if (!e.target.value) return
                      inputRef.current = e.target.value
                      submit()
                    }}
                    className="rounded border border-border bg-background px-2 py-1.5 text-sm text-primary focus:border-accent focus:outline-none"
                  >
                    {/* Present only while the current symbol isn't one of the presets
                        (e.g. still set from an old free-text entry), so the select
                        never silently swaps it out from under the last scan. */}
                    {!SYMBOL_GROUPS.some((g) => g.symbols.includes(symbol)) ? (
                      <option value="">{symbol || 'Pick…'}</option>
                    ) : null}
                    {SYMBOL_GROUPS.map((group) => (
                      <optgroup key={group.label} label={group.label}>
                        {group.symbols.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-[11px] text-muted">
                  Entry timeframe
                  <select
                    value={ltf}
                    onChange={(e) => changeLtf(e.target.value)}
                    className="rounded border border-border bg-background px-2 py-1.5 text-sm text-primary focus:border-accent focus:outline-none"
                  >
                    {LTF_OPTIONS.map((tf) => (
                      <option key={tf} value={tf}>{tf}</option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={submit}
                  disabled={loading}
                  className="rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50"
                  style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
                >
                  {loading ? 'Scanning…' : 'Scan now'}
                </button>
                {data?.ok ? (
                  <button
                    type="button"
                    onClick={copySummary}
                    className="rounded-lg border border-border px-3 py-2 text-xs font-medium text-secondary hover:border-accent/40 hover:text-accent"
                  >
                    {copied ? 'Copied ✓' : 'Copy as Markdown'}
                  </button>
                ) : null}
                {data?.timestamp ? (
                  <span className="text-[11px] text-muted">
                    Updated {new Date(data.timestamp).toLocaleTimeString()} · auto-refreshes every 5 min
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-[10.5px] text-muted">
                Bias is read on 15m, 1h, 4h and 1d. The feed only serves 15m and 1h honestly — it returns 1h candles for a "4h" request and truncates daily history — so 4h and 1d are resampled from 1h bars here rather than requested. A timeframe with too little history reads "unknown" instead of guessing.
              </p>
            </SectionCard>

            {error ? (
              <div className="rounded-lg border border-warning/30 bg-warning/10 p-4 text-xs text-warning">{error}</div>
            ) : null}

            {data?.ok ? (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <SectionCard
                    title="Directional bias by timeframe"
                    info="Each row is the market structure read on that timeframe, from the same swing detector. 15m and 1h come straight from the data feed; 4h and 1d are resampled from 1h bars, because the upstream feed silently serves 1h candles for a '4h' request and truncates daily history. A row reads 'unknown' when there weren't enough bars to confirm two swings — that's a missing reading, not a neutral one. Rows agreeing is a description of the chart, not evidence about what happens next."
                  >
                    {(data.bias_ladder ?? []).length === 0 ? (
                      <p className="text-xs text-muted">No structure data returned.</p>
                    ) : (
                      <>
                        <div className="overflow-x-auto">
                          <table className="w-full text-[11px]">
                            <thead>
                              <tr className="text-left uppercase tracking-wider text-muted">
                                <th className="pb-1 pr-3 font-medium">TF</th>
                                <th className="pb-1 pr-3 font-medium">Direction</th>
                                <th className="pb-1 pr-3 font-medium">Structure</th>
                                <th className="pb-1 font-medium">Bars</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(data.bias_ladder ?? []).map((rung) => (
                                <tr key={rung.timeframe} className="border-t border-border/40">
                                  <td className="py-1 pr-3 font-mono uppercase text-primary">{rung.timeframe}</td>
                                  <td className="py-1 pr-3">
                                    <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${biasTone(rung.sufficient ? rung.bias : null)}`}>
                                      {rung.bias}
                                    </span>
                                  </td>
                                  <td className="py-1 pr-3 text-secondary">
                                    {rung.sufficient ? (rung.recent_sequence || rung.last_break || '—') : 'not enough history'}
                                  </td>
                                  <td className="py-1 font-mono text-muted">{rung.bars}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {data.bias_alignment ? (
                          <p className="mt-2 text-[11px] text-secondary">
                            {data.bias_alignment.verdict === 'mixed' ? (
                              <>Timeframes <span className="font-semibold text-warning">disagree</span> — {data.bias_alignment.bullish} bullish, {data.bias_alignment.bearish} bearish.</>
                            ) : data.bias_alignment.verdict === 'unknown' ? (
                              <>No timeframe has enough history for a structural read.</>
                            ) : (
                              <>All {data.bias_alignment.usable} readable timeframes point <span className={`font-semibold ${data.bias_alignment.verdict === 'bullish' ? 'text-success' : 'text-danger'}`}>{data.bias_alignment.verdict}</span>.</>
                            )}
                          </p>
                        ) : null}
                      </>
                    )}
                  </SectionCard>

                  <SectionCard title="Killzone + draw on liquidity">
                    <p className="text-xs text-secondary">
                      Current: <span className="font-semibold text-primary">{data.current_killzone}</span>
                    </p>
                    <div className="mt-2 grid grid-cols-2 gap-3 text-[11px]">
                      <div>
                        <span className="uppercase tracking-wider text-muted">BSL (above)</span>
                        {(data.htf_liquidity_targets?.bsl ?? []).length === 0 ? (
                          <p className="text-muted">none nearby</p>
                        ) : (
                          data.htf_liquidity_targets!.bsl.map((p, i) => (
                            <p key={i} className="font-mono text-primary">{p.price} <span className="text-muted">({p.distance_from_price} away)</span></p>
                          ))
                        )}
                      </div>
                      <div>
                        <span className="uppercase tracking-wider text-muted">SSL (below)</span>
                        {(data.htf_liquidity_targets?.ssl ?? []).length === 0 ? (
                          <p className="text-muted">none nearby</p>
                        ) : (
                          data.htf_liquidity_targets!.ssl.map((p, i) => (
                            <p key={i} className="font-mono text-primary">{p.price} <span className="text-muted">({p.distance_from_price} away)</span></p>
                          ))
                        )}
                      </div>
                    </div>
                  </SectionCard>
                </div>

                <SectionCard
                  title={`Candidate events (${ltf})`}
                  info="Each row pairs a liquidity sweep with a structure shift that followed shortly after, in the opposing direction — the exact sequence a sweep+MSS setup describes. 'Agrees with HTF' just means the direction matches the 1h bias above; it's not a rating. Hover a row to highlight it on the chart above, with its entry/stop previewed. 'Plan this' seeds the Plan tab with the sweep as a stop reference and the shift as an entry reference — both fully editable."
                >
                  {data.candidates.length === 0 ? (
                    <p className="text-xs text-muted">No sweep + shift events found in the recent window.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="text-[10px] uppercase tracking-wider text-muted">
                            <th className="pb-1.5 pr-3">Direction</th>
                            <th className="pb-1.5 pr-3">Sweep</th>
                            <th className="pb-1.5 pr-3">Shift</th>
                            <th className="pb-1.5 pr-3">Potential entry → target</th>
                            <th className="pb-1.5 pr-3">Killzone</th>
                            <th className="pb-1.5 pr-3">HTF</th>
                            <th className="pb-1.5 pr-3">
                              Confluence
                              <InfoTip text="A 0-5 count of plain, disclosed facts this candidate happens to satisfy (HTF agreement, a named killzone, strong displacement, a quick reaction, R:R to the nearest liquidity target) — not a win probability or a model's confidence. Hover a row's stars for the exact breakdown." />
                            </th>
                            <th className="pb-1.5" />
                          </tr>
                        </thead>
                        <tbody>
                          {data.candidates.map((c, i) => (
                            <tr
                              key={i}
                              onMouseEnter={() => setFocusedIndex(i)}
                              onMouseLeave={() => setFocusedIndex((cur) => (cur === i ? null : cur))}
                              className={`border-t border-border-subtle transition-colors ${focusedIndex === i ? 'bg-accent/5' : ''}`}
                            >
                              <td className="py-1.5 pr-3">
                                <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                                  c.direction === 'bullish' ? 'bg-positive/10 text-positive' : 'bg-negative/10 text-negative'
                                }`}>
                                  {c.direction}
                                </span>
                              </td>
                              <td className="py-1.5 pr-3 font-mono text-secondary">
                                {c.sweep_level} <span className="text-muted">· {fmtTime(c.sweep_time)}</span>
                              </td>
                              <td className="py-1.5 pr-3 font-mono text-secondary">
                                {c.shift_level} <span className="text-muted">· {fmtTime(c.shift_time)}</span>
                              </td>
                              <td className="py-1.5 pr-3 font-mono text-secondary">
                                {c.potential_entry} → {c.potential_target ?? '—'}
                                {c.risk_reward != null ? <span className="text-muted"> · R:R {c.risk_reward}</span> : null}
                              </td>
                              <td className="py-1.5 pr-3 text-secondary">{c.killzone}</td>
                              <td className="py-1.5 pr-3">
                                {c.agrees_with_htf_bias ? (
                                  <span className="text-positive">agrees</span>
                                ) : (
                                  <span className="text-warning">conflicts</span>
                                )}
                              </td>
                              <td className="py-1.5 pr-3">
                                <span title={confluenceTooltip(c)} className={`font-mono tracking-tight ${starTone(c.confluence_score)}`}>
                                  {stars(c.confluence_score)}
                                </span>
                              </td>
                              <td className="py-1.5">
                                <button
                                  type="button"
                                  onClick={() => planThis(c)}
                                  className="rounded border border-accent/40 bg-accent/10 px-2 py-0.5 text-[10.5px] font-medium text-accent hover:bg-accent/20"
                                >
                                  Plan this
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </SectionCard>

                <SectionCard
                  title="Unmitigated fair value gaps"
                  info="Untested FVGs on the entry timeframe — a common place a sweep+MSS entry retraces into. Not filtered by direction or recency beyond the most recent few. Each gap spans three candles: a displacement candle whose neighbors' wicks don't overlap; the time shown is the third candle — the one whose close confirmed the gap exists — not the displacement candle itself."
                >
                  {data.recent_unmitigated_fvgs.length === 0 ? (
                    <p className="text-xs text-muted">None currently unmitigated.</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {data.recent_unmitigated_fvgs.map((f, i) => (
                        <span
                          key={i}
                          className={`rounded border px-2 py-1 text-[11px] font-mono ${
                            f.type === 'Bullish' ? 'border-positive/30 text-positive' : 'border-negative/30 text-negative'
                          }`}
                        >
                          {f.bottom}–{f.top} <span className="text-muted">· confirmed {fmtTime(f.creation_time)} · {f.age_candles} candles ago</span>
                        </span>
                      ))}
                    </div>
                  )}
                </SectionCard>

                <p className="text-[10.5px] text-muted">{data.disclaimer}</p>
              </>
            ) : null}
          </>
        ) : (
          <PreTradeChecklistForm prefill={prefill} />
        )}
      </div>
    </PageContainer>
  )
}
