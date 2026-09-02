import { useIntelligenceCommandCenter } from '../lib/useIntelligence'
import { IntelligenceHeader } from '../components/intelligence/IntelligenceHeader'
import { WhatMattersNow } from '../components/intelligence/WhatMattersNow'
import { OpportunityMap } from '../components/intelligence/OpportunityMap'
import { CrossAssetRegime } from '../components/intelligence/CrossAssetRegime'
import { EconomicHeatmap } from '../components/intelligence/EconomicHeatmap'

/**
 * Market Intelligence Command Center. One coordinated fetch of summary +
 * opportunity map + heatmap; each section renders, loads and fails
 * independently. No fabricated data — sections the API does not expose
 * (change history, correlation feed) are omitted, not invented.
 */
export function IntelligencePage() {
  const cc = useIntelligenceCommandCenter()

  return (
    <div className="w-full space-y-4 px-4 py-4 sm:px-6">
      <IntelligenceHeader section={cc.summary} />

      <div className="flex items-center justify-end gap-3 text-[11px] text-muted">
        {cc.refreshing ? <span aria-live="polite">Refreshing…</span> : null}
        <button
          type="button"
          onClick={cc.refetch}
          className="rounded border border-border px-2 py-1 text-xs text-primary hover:bg-surface-hover"
        >
          Refresh
        </button>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <WhatMattersNow summary={cc.summary} opportunity={cc.opportunity} />
        <CrossAssetRegime section={cc.summary} onRetry={cc.refetch} />
      </div>

      <OpportunityMap section={cc.opportunity} onRetry={cc.refetch} />

      <EconomicHeatmap section={cc.heatmap} onRetry={cc.refetch} />

      <p className="pb-4 text-[11px] text-muted">
        Market intelligence is contextual research — it is not an order signal.
        Not exposed by the current API: rolling correlations, market-change
        history.
      </p>
    </div>
  )
}
