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
            className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
          >
            Market workspace
          </Link>
          <Link
            to={`/workspace/risk?symbol=${encodeURIComponent(symbol)}`}
            className="rounded border border-accent/50 bg-accent/10 px-2.5 py-1 text-xs font-semibold text-accent hover:bg-accent/20"
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
