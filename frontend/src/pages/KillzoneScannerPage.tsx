import { useCallback, useEffect, useRef, useState } from 'react'
import { PageContainer } from '../components/shell/PageContainer'
import { SectionCard } from '../components/intelligence/primitives'
import { scanKillzone } from '../api/scanner'
import type { KillzoneScanResponse } from '../types/scanner'

const LTF_OPTIONS = ['1m', '5m', '15m', '1h']
const REFRESH_MS = 5 * 60 * 1000
const SYMBOL_KEY = 'tl.scanner.symbol'
const LTF_KEY = 'tl.scanner.ltf'

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

/**
 * Killzone Scanner (`/workspace/killzone-scanner`). Flags candidate liquidity-
 * sweep + market-structure-shift events, tagged with the ICT killzone window
 * they fell in and whether they agree with the higher-timeframe structural
 * bias. Pattern-flagging only — never a signal, never a recommendation, no
 * execution path. Every threshold behind a flag is plain and disclosed (see
 * killzone_scanner.py) — this replaces staring at charts, not judgment.
 */
export function KillzoneScannerPage() {
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

  const load = useCallback((sym: string, timeframe: string, signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    scanKillzone(sym.trim().toUpperCase(), timeframe, signal)
      .then((r) => {
        if (signal?.aborted) return
        setData(r)
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

  return (
    <PageContainer
      title="Killzone Scanner"
      description="Flags candidate liquidity-sweep + structure-shift events and checks them against the higher-timeframe bias and the active ICT killzone. Pattern-flagging only — it replaces staring at charts, not your own judgment on whether a flagged event is actually worth trading."
    >
      <div className="space-y-4">
        <SectionCard title="Scan">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-[11px] text-muted">
              Symbol
              <input
                type="text"
                defaultValue={symbol}
                onChange={(e) => {
                  inputRef.current = e.target.value
                }}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
                className="w-32 rounded border border-border bg-background px-2 py-1.5 text-sm text-primary focus:border-accent focus:outline-none"
              />
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
            {data?.timestamp ? (
              <span className="text-[11px] text-muted">
                Updated {new Date(data.timestamp).toLocaleTimeString()} · auto-refreshes every 5 min
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-[10.5px] text-muted">
            Bias timeframe is fixed to 1h — the upstream feed doesn't reliably serve enough daily/4h history for structure detection (see killzone_scanner.py).
          </p>
        </SectionCard>

        {error ? (
          <div className="rounded-lg border border-warning/30 bg-warning/10 p-4 text-xs text-warning">{error}</div>
        ) : null}

        {data?.ok ? (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <SectionCard title="Higher-timeframe bias (1h)">
                <div className="flex items-center gap-2">
                  <span className={`rounded border px-2 py-0.5 text-xs font-semibold uppercase ${biasTone(data.htf_bias)}`}>
                    {data.htf_bias ?? 'unknown'}
                  </span>
                  <span className="text-xs text-secondary">{data.htf_structure?.recent_sequence}</span>
                </div>
                <p className="mt-2 text-xs text-secondary">{data.htf_structure?.last_break}</p>
                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-muted">Last swing high</span>
                    <p className="font-mono text-primary">{data.htf_structure?.last_swing_high ?? '—'}</p>
                  </div>
                  <div>
                    <span className="text-muted">Last swing low</span>
                    <p className="font-mono text-primary">{data.htf_structure?.last_swing_low ?? '—'}</p>
                  </div>
                </div>
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
              info="Each row pairs a liquidity sweep with a structure shift that followed shortly after, in the opposing direction — the exact sequence a sweep+MSS setup describes. 'Agrees with HTF' just means the direction matches the 1h bias above; it's not a rating."
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
                        <th className="pb-1.5 pr-3">Killzone</th>
                        <th className="pb-1.5">HTF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.candidates.map((c, i) => (
                        <tr key={i} className="border-t border-border-subtle">
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
                          <td className="py-1.5 pr-3 text-secondary">{c.killzone}</td>
                          <td className="py-1.5">
                            {c.agrees_with_htf_bias ? (
                              <span className="text-positive">agrees</span>
                            ) : (
                              <span className="text-warning">conflicts</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </SectionCard>

            <SectionCard title="Unmitigated fair value gaps" info="Untested FVGs on the entry timeframe — a common place a sweep+MSS entry retraces into. Not filtered by direction or recency beyond the most recent few.">
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
                      {f.bottom}–{f.top}
                    </span>
                  ))}
                </div>
              )}
            </SectionCard>

            <p className="text-[10.5px] text-muted">{data.disclaimer}</p>
          </>
        ) : null}
      </div>
    </PageContainer>
  )
}
