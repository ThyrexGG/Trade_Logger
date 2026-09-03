import { useEffect, useRef, useState } from 'react'
import { getMacroProviders } from '../../api/macro'
import type { MacroProvidersResponse } from '../../types/macro'
import type { LoadState } from '../../lib/useWatchlist'
import { SectionCard } from '../intelligence/primitives'
import { OpsStatusTag, OpsUnavailable } from '../operations/primitives'

const CATEGORIES = ['growth', 'jobs', 'inflation', 'cot', 'sentiment']
const CAT_LABEL: Record<string, string> = {
  growth: 'Growth',
  jobs: 'Jobs',
  inflation: 'Inflation',
  cot: 'COT',
  sentiment: 'Sentiment',
}

function stateTone(s: string): 'positive' | 'negative' | 'warning' | 'neutral' {
  if (s === 'LIVE') return 'positive'
  if (s === 'PROVIDER_UNAVAILABLE' || s === 'NONE') return 'negative'
  if (s === 'CONFLICT' || s === 'SEED_DEMO' || s === 'LIVE_STALE') return 'warning'
  return 'neutral'
}
function cell(s: string): string {
  switch (s) {
    case 'LIVE':
      return 'bg-positive/15 text-positive'
    case 'SEED_DEMO':
      return 'bg-warning/15 text-warning'
    case 'CONFLICT':
      return 'bg-warning/25 text-warning'
    case 'PROVIDER_UNAVAILABLE':
    case 'NONE':
      return 'bg-negative/15 text-negative'
    default:
      return 'bg-surface-elevated/40 text-muted'
  }
}

/**
 * Phase 66 — "Providers & coverage" panel. Progressive disclosure: the coverage
 * matrix and conflicts up top, per-provider health collapsed below. Read-only;
 * never shows a secret (the API never returns one).
 */
export function MacroProviders() {
  const [data, setData] = useState<MacroProvidersResponse | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState<string | null>(null)
  const [openProv, setOpenProv] = useState<string | null>(null)
  const hasData = useRef(false)

  useEffect(() => {
    let disposed = false
    const controller = new AbortController()
    if (!hasData.current) setState('loading')
    getMacroProviders(controller.signal)
      .then((d) => {
        if (disposed) return
        setData(d)
        setState('ready')
        hasData.current = true
        setError(null)
      })
      .catch((e) => {
        if (disposed || controller.signal.aborted) return
        setError(String(e?.message ?? e))
        if (!hasData.current) setState('error')
      })
    return () => {
      disposed = true
      controller.abort()
    }
  }, [])

  if (state === 'loading') {
    return <div className="rounded-lg border border-border bg-surface p-6 text-center text-xs text-muted">Loading providers…</div>
  }
  if (state === 'error' || !data) {
    return (
      <div className="rounded-lg border border-negative/30 bg-negative/10 p-4 text-xs text-negative">
        {error ?? 'Provider diagnostics unavailable.'}
      </div>
    )
  }

  const economies = Object.keys(data.coverage)

  return (
    <div className="space-y-4">
      <SectionCard
        title="Evidence coverage"
        action={<span className="font-mono text-[10px] text-muted">base: {data.base_provider ?? '—'}</span>}
      >
        <p className="mb-2 text-[11px] text-muted">
          What each scorecard category is backed by, per economy. <span className="text-positive">LIVE</span> = real
          provider data · <span className="text-warning">SEED_DEMO</span> = seeded shape ·{' '}
          <span className="text-warning">CONFLICT</span> = sources disagree ·{' '}
          <span className="text-muted">INSUFFICIENT_EVIDENCE</span> = no source (not zero).
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[11px]">
            <thead className="text-muted">
              <tr>
                <th className="px-2 py-1 text-left font-medium">Economy</th>
                {CATEGORIES.map((c) => (
                  <th key={c} className="px-2 py-1 text-center font-medium">{CAT_LABEL[c]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {economies.map((ccy) => (
                <tr key={ccy} className="border-t border-border-subtle/50">
                  <td className="px-2 py-1 font-mono text-primary">{ccy}</td>
                  {CATEGORIES.map((c) => {
                    const s = data.coverage[ccy]?.[c] ?? '—'
                    return (
                      <td key={c} className="px-1 py-1 text-center">
                        <span className={`inline-block rounded px-1.5 py-0.5 font-mono text-[9px] uppercase ${cell(s)}`}>
                          {s === 'INSUFFICIENT_EVIDENCE' ? 'none' : s.toLowerCase().replace('provider_', '')}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {data.conflicts.length > 0 ? (
        <SectionCard title={`Conflicts (${data.conflicts.length})`}>
          <ul className="space-y-1 text-[11px]">
            {data.conflicts.map((c, i) => (
              <li key={i} className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-warning">
                <span className="font-mono">{c.country} {c.metric} {c.period}</span> · {c.field}: sources disagree —
                using <span className="font-semibold">{c.selected_source}</span> = {c.selected_value}.
                <span className="ml-1 text-muted">
                  ({c.claims.map((cl) => `${cl.source}=${cl.value}`).join(', ')})
                </span>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      <SectionCard title="Providers">
        {data.providers.length === 0 ? (
          <OpsUnavailable>No providers registered.</OpsUnavailable>
        ) : (
          <div className="space-y-2">
            {data.providers.map((p) => {
              const hs = p.health?.provider_state ?? (p.configured ? 'PENDING' : 'NOT_CONFIGURED')
              const open = openProv === p.key
              return (
                <div key={p.key} className="rounded border border-border-subtle">
                  <button
                    type="button"
                    onClick={() => setOpenProv(open ? null : p.key)}
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
                  >
                    <span className="min-w-0">
                      <span className="font-mono text-xs text-primary">{p.key}</span>
                      <span className="ml-2 text-[11px] text-muted">{p.name}</span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      {!p.configured ? (
                        <span className="font-mono text-[10px] uppercase text-muted">not configured</span>
                      ) : (
                        <OpsStatusTag value={hs} tone={stateTone(hs)} size="sm" />
                      )}
                      <span className="text-muted">{open ? '−' : '+'}</span>
                    </span>
                  </button>
                  {open ? (
                    <div className="border-t border-border-subtle px-3 py-2 text-[11px]">
                      <p className="text-muted">
                        capabilities: <span className="font-mono text-secondary">{p.capabilities.join(', ') || '—'}</span>
                      </p>
                      {p.health?.reason ? <p className="mt-1 text-muted">{p.health.reason}</p> : null}
                      <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 font-mono text-[10px] text-muted sm:grid-cols-3">
                        {p.health?.records_registered != null ? <span>records: {p.health.records_registered}</span> : null}
                        {p.health?.latency_ms != null ? <span>latency: {p.health.latency_ms} ms</span> : null}
                        {p.health?.last_success ? <span>ok: {p.health.last_success.slice(0, 16).replace('T', ' ')}</span> : null}
                        {p.health?.last_failure ? <span>fail: {p.health.last_failure.slice(0, 16).replace('T', ' ')}</span> : null}
                        {p.health?.last_error ? <span className="text-negative">err: {p.health.last_error}</span> : null}
                        {p.health?.backoff_until_sec ? <span>backoff: {Math.round(p.health.backoff_until_sec)}s</span> : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </SectionCard>

      <p className="border-t border-border-subtle pt-2 text-[10px] text-muted">
        {data.disclaimer} Conflict precedence: official agency / central bank &gt; FRED/ALFRED &gt;
        OECD-harmonised &gt; other. No secret (API key / token) is ever included here.
      </p>
    </div>
  )
}
