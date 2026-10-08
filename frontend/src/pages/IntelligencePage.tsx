import { useIntelligenceCommandCenter } from '../lib/useIntelligence'
import { IntelligenceHeader } from '../components/intelligence/IntelligenceHeader'
import { WhatMattersNow } from '../components/intelligence/WhatMattersNow'
import { OpportunityMap } from '../components/intelligence/OpportunityMap'
import { CrossAssetRegime } from '../components/intelligence/CrossAssetRegime'
import { EconomicHeatmap } from '../components/intelligence/EconomicHeatmap'
import { MarketPlainView } from '../components/intelligence/MarketPlainView'
import { MoreDetails, PageGuide } from '../components/shared/PageGuide'

/**
 * Market Intelligence. A plain-English view first (the mood, the dollar, and
 * each market's lean and why), with the original analyst panels — regime
 * scores, opportunity rankings, economic heatmap — one click away under
 * "Show the detailed numbers". Same single coordinated fetch for both.
 */
export function IntelligencePage() {
  const cc = useIntelligenceCommandCenter()

  return (
    <div className="w-full space-y-4 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-lg font-semibold text-primary">Market Intelligence</h1>
        <div className="flex items-center gap-3 text-[11px] text-muted">
          {cc.refreshing ? <span aria-live="polite">Refreshing…</span> : null}
          <button type="button" onClick={cc.refetch} className="tl-btn tl-btn--secondary tl-btn--sm">
            Refresh
          </button>
        </div>
      </div>

      <PageGuide
        id="market-intelligence"
        title="What's the market in the mood for, and which way is each market leaning?"
        steps={[
          'Start with "The big picture" — the overall mood decides a lot of what happens everywhere else.',
          '"Markets at a glance" shows each market’s lean and the main reason for it. Tap one for the full story.',
          'Use it as background before you plan a trade, not as a buy or sell button.',
        ]}
      />

      <MarketPlainView summary={cc.summary} opportunity={cc.opportunity} onRetry={cc.refetch} />

      <MoreDetails summary="Show the detailed numbers" hint="regime scores, full rankings with filters, economic data heatmap">
        <IntelligenceHeader section={cc.summary} />
        <div className="grid gap-4 xl:grid-cols-2">
          <WhatMattersNow summary={cc.summary} opportunity={cc.opportunity} />
          <CrossAssetRegime section={cc.summary} onRetry={cc.refetch} />
        </div>
        <OpportunityMap section={cc.opportunity} onRetry={cc.refetch} />
        <EconomicHeatmap section={cc.heatmap} onRetry={cc.refetch} />
      </MoreDetails>
    </div>
  )
}
