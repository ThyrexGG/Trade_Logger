import { useState } from 'react'
import { useMacroIntelligence } from '../lib/useMacroIntelligence'
import { PageContainer } from '../components/shell/PageContainer'
import {
  MacroAssets,
  MacroCalendar,
  MacroCurrencies,
  MacroOverview,
  ProvenanceBanner,
} from '../components/macro/MacroViews'
import { MacroScorecard } from '../components/macro/MacroScorecard'
import { MacroHeatmap } from '../components/macro/MacroHeatmap'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

type Tab = 'scorecard' | 'heatmap' | 'overview' | 'calendar' | 'currencies' | 'assets'
const TABS: { id: Tab; label: string }[] = [
  { id: 'scorecard', label: 'Scorecard' },
  { id: 'heatmap', label: 'Economic Heatmap' },
  { id: 'overview', label: 'Overview' },
  { id: 'calendar', label: 'Economic Calendar' },
  { id: 'currencies', label: 'Currency Strength' },
  { id: 'assets', label: 'Asset Macro Context' },
]

/**
 * Macro / Market Intelligence (`/research/macro`). TradeLogger's own read-only
 * macro dashboard over the deterministic macro engines + provider layer. Every
 * panel states its data provenance; nothing demo is presented as real.
 */
export function MacroIntelligencePage() {
  const { overview, currencies, assets, events, state, error, refreshing, refetch } = useMacroIntelligence()
  const [tab, setTab] = useState<Tab>('scorecard')

  const env = overview ?? currencies ?? assets ?? events

  return (
    <PageContainer
      title="Macro Intelligence"
      description="Economic calendar, surprise, currency strength and asset macro context — deterministic, read-only, and explicitly labelled by data provenance."
      actions={
        <div className="flex items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Refreshing…</span> : null}
          <button type="button" onClick={refetch} className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Refresh
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <OpsSafetyBanner />
        <ProvenanceBanner env={env} />

        <div className="flex flex-wrap gap-1 border-b border-border-subtle">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded-t border-b-2 px-3 py-1.5 text-xs ${
                tab === t.id ? 'border-accent text-accent' : 'border-transparent text-secondary hover:text-primary'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'scorecard' && <MacroScorecard />}
        {tab === 'heatmap' && <MacroHeatmap />}

        {tab !== 'scorecard' && tab !== 'heatmap' ? (
          state === 'loading' ? (
            <div className="rounded-lg border border-border bg-surface p-4"><SkeletonRows rows={8} /></div>
          ) : state === 'error' ? (
            <div className="rounded-lg border border-border bg-surface p-4">
              <SectionError message={error ?? 'The macro service could not be reached.'} onRetry={refetch} />
            </div>
          ) : (
            <>
              {error ? (
                <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                  Some sections failed to refresh: {error}
                </p>
              ) : null}
              {tab === 'overview' && (overview ? <MacroOverview data={overview} /> : <SkeletonRows rows={6} />)}
              {tab === 'calendar' && (events ? <MacroCalendar data={events} /> : <SkeletonRows rows={6} />)}
              {tab === 'currencies' && (currencies ? <MacroCurrencies data={currencies} /> : <SkeletonRows rows={6} />)}
              {tab === 'assets' && (assets ? <MacroAssets data={assets} /> : <SkeletonRows rows={6} />)}
            </>
          )
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          Macro intelligence is deterministic context, not a forecast and never an execution
          signal. Currencies without provider releases return{' '}
          <code>INSUFFICIENT_EVIDENCE</code>. Connect a real feed via the{' '}
          <code>MACRO_DATA_PROVIDER</code> environment variable — no app changes needed.
        </p>
      </div>
    </PageContainer>
  )
}
