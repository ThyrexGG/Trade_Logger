import { Link, useParams } from 'react-router-dom'
import { useAssetProfile } from '../lib/useAssetProfile'
import { useAssetIntelligence } from '../lib/useAssetIntelligence'
import { PageContainer } from '../components/shell/PageContainer'
import { AssetProfile } from '../components/intelligence/AssetProfile'
import { EvidenceFusionPanel } from '../components/intelligence/EvidenceFusionPanel'

/**
 * Asset Intelligence detail. Fetches ONE asset-profile endpoint for the routed
 * symbol — never the whole universe. Race-safe via useAssetProfile.
 */
export function AssetProfilePage() {
  const { symbol: raw } = useParams<{ symbol: string }>()
  const symbol = (raw ?? '').toUpperCase()
  const profile = useAssetProfile(symbol || null)
  const evidence = useAssetIntelligence(symbol || null)

  return (
    <PageContainer
      title={symbol ? `${symbol} — Asset Intelligence` : 'Asset Intelligence'}
      description="Authoritative multi-factor context. Research only — nothing is executed."
      actions={
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/workspace/market?symbol=${encodeURIComponent(symbol)}`}
            className="tl-btn tl-btn--secondary tl-btn--sm"
          >
            Market workspace
          </Link>
          <Link
            to={`/workspace/risk?symbol=${encodeURIComponent(symbol)}`}
            className="tl-btn tl-btn--primary tl-btn--sm"
          >
            Plan risk
          </Link>
        </div>
      }
    >
      <div className="mb-4">
        <Link
          to="/research/intelligence"
          className="text-xs text-secondary hover:text-primary"
        >
          ← Back to Market Intelligence
        </Link>
      </div>

      <div className="space-y-4">
        <AssetProfile
          symbol={symbol}
          state={profile.state}
          data={profile.data}
          error={profile.error}
          refreshing={profile.refreshing}
          onRetry={profile.refetch}
        />

        <EvidenceFusionPanel
          symbol={symbol}
          state={evidence.state}
          data={evidence.data}
          error={evidence.error}
          refreshing={evidence.refreshing}
          onRetry={evidence.refetch}
        />
      </div>
    </PageContainer>
  )
}
