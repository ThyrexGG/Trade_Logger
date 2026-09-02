import { Link } from 'react-router-dom'
import { PageContainer } from '../components/shell/PageContainer'

export function NotFoundPage() {
  return (
    <PageContainer title="Page not found" width="standard">
      <p className="text-sm text-secondary">
        That route is not part of the TradeLogger terminal.
      </p>
      <Link
        to="/workspace"
        className="mt-4 inline-block rounded border border-border px-3 py-1.5 text-sm text-primary hover:bg-surface-hover"
      >
        Go to Trading Workspace
      </Link>
    </PageContainer>
  )
}
