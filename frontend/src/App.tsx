import type { ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/shell/AppShell'
import { ALL_NAV_ITEMS } from './lib/navigation'
import { MarketWorkspacePage } from './pages/MarketWorkspacePage'
import { RiskGatewayPage } from './pages/RiskGatewayPage'
import { IntelligencePage } from './pages/IntelligencePage'
import { AssetProfilePage } from './pages/AssetProfilePage'
import { EvidenceCommandCenterPage } from './pages/EvidenceCommandCenterPage'
import { ForwardEvidencePage } from './pages/ForwardEvidencePage'
import { EvidenceStatisticsPage } from './pages/EvidenceStatisticsPage'
import { EvidenceGovernancePage } from './pages/EvidenceGovernancePage'
import { StrategyLabPage } from './pages/StrategyLabPage'
import { BacktestWorkspacePage } from './pages/BacktestWorkspacePage'
import { PositionsPage } from './pages/PositionsPage'
import { PriceAlertsPage } from './pages/PriceAlertsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { JournalPage } from './pages/JournalPage'
import { AuditPage } from './pages/AuditPage'
import { OperationsOverviewPage } from './pages/OperationsOverviewPage'
import { ZoneOverviewPage } from './pages/ZoneOverviewPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { SystemHealthPage } from './pages/SystemHealthPage'
import { NotFoundPage } from './pages/NotFoundPage'

/** Item routes whose page is implemented for real (not a placeholder). */
const LIVE_ITEM_PAGES: Record<string, ReactElement> = {
  'workspace.market': <MarketWorkspacePage />,
  'workspace.risk': <RiskGatewayPage />,
  'workspace.positions': <PositionsPage />,
  'workspace.alerts': <PriceAlertsPage />,
  'workspace.analytics': <AnalyticsPage />,
  'research.intelligence': <IntelligencePage />,
  'research.strategy': <StrategyLabPage />,
  'research.backtest': <BacktestWorkspacePage />,
  'evidence.forward': <ForwardEvidencePage />,
  'evidence.statistics': <EvidenceStatisticsPage />,
  'evidence.governance': <EvidenceGovernancePage />,
  'operations.journal': <JournalPage />,
  'operations.audit': <AuditPage />,
  'operations.system': <SystemHealthPage />,
}

/**
 * Routing foundation. All routes render inside the persistent <AppShell>.
 * Nested item routes are generated from the navigation model so future stages
 * only swap a placeholder for a real page.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Navigate to="/workspace" replace />} />

        <Route path="workspace" element={<MarketWorkspacePage />} />
        <Route path="research" element={<ZoneOverviewPage zoneId="research" />} />
        <Route path="evidence" element={<EvidenceCommandCenterPage />} />
        <Route path="operations" element={<OperationsOverviewPage />} />

        {ALL_NAV_ITEMS.map((item) => (
          <Route
            key={item.id}
            path={item.path.slice(1)}
            element={
              LIVE_ITEM_PAGES[item.id] ?? <PlaceholderPage itemId={item.id} />
            }
          />
        ))}

        <Route
          path="research/intelligence/asset/:symbol"
          element={<AssetProfilePage />}
        />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
