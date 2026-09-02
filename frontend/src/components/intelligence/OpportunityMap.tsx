import { useId, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import type {
  OpportunityMapItem,
  OpportunityMapResponse,
} from '../../types/intelligence'
import type { Section } from '../../lib/useIntelligence'
import { FreshnessBadge, IntelTag, SectionCard, SectionError, SkeletonRows } from './primitives'

type SortKey = 'rank' | 'edge_score' | 'macro_score' | 'agreement_pct' | 'data_quality_score'

interface Ranked extends OpportunityMapItem {
  rank: number
}

function useFilters(items: Ranked[]) {
  const [query, setQuery] = useState('')
  const [assetClass, setAssetClass] = useState('ALL')
  const [context, setContext] = useState('ALL')
  const [conflict, setConflict] = useState('ALL')
  const [eligibleOnly, setEligibleOnly] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('rank')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const classes = useMemo(
    () => ['ALL', ...Array.from(new Set(items.map((i) => i.asset_class))).sort()],
    [items],
  )
  const contexts = useMemo(
    () => ['ALL', ...Array.from(new Set(items.map((i) => i.context_state))).sort()],
    [items],
  )
  const conflicts = useMemo(
    () => ['ALL', ...Array.from(new Set(items.map((i) => i.conflict_state))).sort()],
    [items],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const rows = items.filter((i) => {
      if (q && !i.symbol.toLowerCase().includes(q)) return false
      if (assetClass !== 'ALL' && i.asset_class !== assetClass) return false
      if (context !== 'ALL' && i.context_state !== context) return false
      if (conflict !== 'ALL' && i.conflict_state !== conflict) return false
      if (eligibleOnly && !i.ranking_eligible) return false
      return true
    })
    const dir = sortDir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const av = sortKey === 'rank' ? a.rank : a[sortKey]
      const bv = sortKey === 'rank' ? b.rank : b[sortKey]
      return (av - bv) * dir
    })
  }, [items, query, assetClass, context, conflict, eligibleOnly, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(key)
      setSortDir(key === 'rank' ? 'asc' : 'desc')
    }
  }

  return {
    query, setQuery,
    assetClass, setAssetClass, classes,
    context, setContext, contexts,
    conflict, setConflict, conflicts,
    eligibleOnly, setEligibleOnly,
    sortKey, sortDir, toggleSort,
    filtered,
  }
}

function Th({
  children,
  sortKey,
  active,
  dir,
  onSort,
  className = '',
}: {
  children: ReactNode
  sortKey?: SortKey
  active?: boolean
  dir?: 'asc' | 'desc'
  onSort?: (k: SortKey) => void
  className?: string
}) {
  if (!sortKey) {
    return (
      <th className={`px-2 py-1.5 text-left font-medium ${className}`}>{children}</th>
    )
  }
  return (
    <th className={`px-2 py-1.5 text-left font-medium ${className}`}>
      <button
        type="button"
        onClick={() => onSort?.(sortKey)}
        className="inline-flex items-center gap-1 hover:text-primary"
        aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}
      >
        {children}
        {active ? <span aria-hidden="true">{dir === 'asc' ? '▲' : '▼'}</span> : null}
      </button>
    </th>
  )
}

export function OpportunityMap({
  section,
  onRetry,
}: {
  section: Section<OpportunityMapResponse>
  onRetry: () => void
}) {
  const navigate = useNavigate()
  const searchId = useId()
  const data = section.data

  const ranked: Ranked[] = useMemo(
    () => (data?.ranked_assets ?? []).map((a, i) => ({ ...a, rank: i + 1 })),
    [data],
  )
  const f = useFilters(ranked)

  const open = (symbol: string) =>
    navigate(`/research/intelligence/asset/${encodeURIComponent(symbol)}`)

  let body: ReactNode
  if (section.state === 'loading' && !data) {
    body = <SkeletonRows rows={8} />
  } else if (section.state === 'error' && !data) {
    body = <SectionError message={section.error} onRetry={onRetry} />
  } else if (ranked.length === 0) {
    body = <p className="text-sm text-muted">No ranked instruments returned.</p>
  } else {
    body = (
      <>
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={searchId} className="sr-only">
            Search instruments
          </label>
          <input
            id={searchId}
            value={f.query}
            onChange={(e) => f.setQuery(e.target.value)}
            placeholder="Search symbol…"
            autoComplete="off"
            className="w-36 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:outline-none focus:border-accent"
          />
          <FilterSelect label="Class" value={f.assetClass} onChange={f.setAssetClass} options={f.classes} />
          <FilterSelect label="Context" value={f.context} onChange={f.setContext} options={f.contexts} />
          <FilterSelect label="Conflict" value={f.conflict} onChange={f.setConflict} options={f.conflicts} />
          <label className="flex items-center gap-1.5 text-xs text-secondary">
            <input
              type="checkbox"
              checked={f.eligibleOnly}
              onChange={(e) => f.setEligibleOnly(e.target.checked)}
            />
            Eligible only
          </label>
          <span className="ml-auto text-[11px] tabular-nums text-muted">
            {f.filtered.length}/{ranked.length}
          </span>
        </div>

        {f.filtered.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No instruments match the filters.</p>
        ) : (
          <>
            {/* Desktop / tablet table */}
            <div className="mt-3 hidden overflow-x-auto md:block">
              <table className="w-full border-collapse text-xs">
                <thead className="border-b border-border-subtle text-muted">
                  <tr>
                    <Th sortKey="rank" active={f.sortKey === 'rank'} dir={f.sortDir} onSort={f.toggleSort}>#</Th>
                    <Th>Symbol</Th>
                    <Th>Class</Th>
                    <Th sortKey="edge_score" active={f.sortKey === 'edge_score'} dir={f.sortDir} onSort={f.toggleSort} className="text-right">Edge</Th>
                    <Th sortKey="macro_score" active={f.sortKey === 'macro_score'} dir={f.sortDir} onSort={f.toggleSort} className="text-right">Macro</Th>
                    <Th sortKey="agreement_pct" active={f.sortKey === 'agreement_pct'} dir={f.sortDir} onSort={f.toggleSort} className="text-right">Agree</Th>
                    <Th>Context</Th>
                    <Th>Dominant driver</Th>
                    <Th>Conflict</Th>
                    <Th sortKey="data_quality_score" active={f.sortKey === 'data_quality_score'} dir={f.sortDir} onSort={f.toggleSort} className="text-right">DQ</Th>
                  </tr>
                </thead>
                <tbody>
                  {f.filtered.map((r) => (
                    <tr
                      key={r.symbol}
                      tabIndex={0}
                      onClick={() => open(r.symbol)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          open(r.symbol)
                        }
                      }}
                      className="cursor-pointer border-b border-border-subtle/60 hover:bg-surface-elevated focus:bg-surface-elevated focus:outline-none"
                    >
                      <td className="px-2 py-1.5 font-mono tabular-nums text-muted">{r.rank}</td>
                      <td className="px-2 py-1.5 font-mono font-semibold text-primary">
                        {r.symbol}
                        {!r.ranking_eligible ? (
                          <span className="ml-1 rounded bg-surface px-1 text-[9px] uppercase text-muted">
                            ineligible
                          </span>
                        ) : null}
                      </td>
                      <td className="px-2 py-1.5 text-muted">{r.asset_class}</td>
                      <td className={`px-2 py-1.5 text-right font-mono tabular-nums ${r.edge_score >= 0 ? 'text-positive' : 'text-negative'}`}>
                        {r.edge_score > 0 ? '+' : ''}{r.edge_score.toFixed(1)}
                      </td>
                      <td className={`px-2 py-1.5 text-right font-mono tabular-nums ${r.macro_score >= 0 ? 'text-positive' : 'text-negative'}`}>
                        {r.macro_score > 0 ? '+' : ''}{r.macro_score.toFixed(1)}
                      </td>
                      <td className="px-2 py-1.5 text-right font-mono tabular-nums text-secondary">
                        {r.agreement_pct.toFixed(0)}%
                      </td>
                      <td className="px-2 py-1.5"><IntelTag value={r.context_state} /></td>
                      <td className="px-2 py-1.5 text-secondary">{r.dominant_driver}</td>
                      <td className="px-2 py-1.5"><IntelTag value={r.conflict_state} /></td>
                      <td className="px-2 py-1.5 text-right font-mono tabular-nums text-secondary">
                        {r.data_quality_score}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <ul className="mt-3 space-y-2 md:hidden">
              {f.filtered.map((r) => (
                <li key={r.symbol}>
                  <button
                    type="button"
                    onClick={() => open(r.symbol)}
                    className="w-full rounded border border-border-subtle bg-surface-elevated/40 p-2.5 text-left hover:bg-surface-elevated"
                  >
                    <div className="flex items-baseline justify-between">
                      <span className="font-mono font-semibold text-primary">
                        <span className="mr-1.5 text-muted">#{r.rank}</span>
                        {r.symbol}
                      </span>
                      <span className={`font-mono text-sm tabular-nums ${r.edge_score >= 0 ? 'text-positive' : 'text-negative'}`}>
                        {r.edge_score > 0 ? '+' : ''}{r.edge_score.toFixed(1)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] text-muted">{r.asset_class}</span>
                      <IntelTag value={r.context_state} />
                      <IntelTag value={r.conflict_state} />
                      <span className="text-[11px] text-muted">DQ {r.data_quality_score}</span>
                    </div>
                    <p className="mt-1 text-[11px] text-secondary">{r.dominant_driver}</p>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </>
    )
  }

  return (
    <SectionCard
      title="Opportunity map & rankings"
      action={data ? <FreshnessBadge timestamp={data.timestamp} /> : null}
    >
      {body}
    </SectionCard>
  )
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: string[]
}) {
  return (
    <label className="flex items-center gap-1 text-[11px] text-muted">
      <span className="uppercase tracking-wide">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-border bg-background px-1.5 py-1 text-xs text-primary focus:outline-none focus:border-accent"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  )
}
