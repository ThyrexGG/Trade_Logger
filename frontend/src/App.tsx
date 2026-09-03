import { lazy, Suspense, type ComponentType, type ReactElement } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/shell/AppShell'
import { RouteFallback } from './components/shell/RouteFallback'
import { ALL_NAV_ITEMS } from './lib/navigation'
// The default landing view and the lightweight zone/overview pages stay in the
// main bundle so the first paint after load needs no extra round-trip.
import { MarketWorkspacePage } from './pages/MarketWorkspacePage'
import { ZoneOverviewPage } from './pages/ZoneOverviewPage'
import { OperationsOverviewPage } from './pages/OperationsOverviewPage'
import { EvidenceCommandCenterPage } from './pages/EvidenceCommandCenterPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { NotFoundPage } from './pages/NotFoundPage'

/**
 * Every other page is split into its own chunk and fetched on first navigation
 * to that route. The pages use named exports, so each loader re-maps to
 * `default` for `React.lazy`.
 */
function page(loader: () => Promise<Record<string, ComponentType>>, key: string) {
  return lazy(async () => ({ default: (await loader())[key] }))
}

const RiskGatewayPage = page(() => import('./pages/RiskGatewayPage'), 'RiskGatewayPage')
const IntelligencePage = page(() => import('./pages/IntelligencePage'), 'IntelligencePage')
const AssetProfilePage = page(() => import('./pages/AssetProfilePage'), 'AssetProfilePage')
const ForwardEvidencePage = page(() => import('./pages/ForwardEvidencePage'), 'ForwardEvidencePage')
const EvidenceStatisticsPage = page(() => import('./pages/EvidenceStatisticsPage'), 'EvidenceStatisticsPage')
const EvidenceGovernancePage = page(() => import('./pages/EvidenceGovernancePage'), 'EvidenceGovernancePage')
const StrategyLabPage = page(() => import('./pages/StrategyLabPage'), 'StrategyLabPage')
const BacktestWorkspacePage = page(() => import('./pages/BacktestWorkspacePage'), 'BacktestWorkspacePage')
const ResearchAuditPage = page(() => import('./pages/ResearchAuditPage'), 'ResearchAuditPage')
const MacroIntelligencePage = page(() => import('./pages/MacroIntelligencePage'), 'MacroIntelligencePage')
const PositionsPage = page(() => import('./pages/PositionsPage'), 'PositionsPage')
const PriceAlertsPage = page(() => import('./pages/PriceAlertsPage'), 'PriceAlertsPage')
const AnalyticsPage = page(() => import('./pages/AnalyticsPage'), 'AnalyticsPage')
const CommandCenterPage = page(() => import('./pages/CommandCenterPage'), 'CommandCenterPage')
const AssistantPage = page(() => import('./pages/AssistantPage'), 'AssistantPage')
const JournalPage = page(() => import('./pages/JournalPage'), 'JournalPage')
const AuditPage = page(() => import('./pages/AuditPage'), 'AuditPage')
const SystemHealthPage = page(() => import('./pages/SystemHealthPage'), 'SystemHealthPage')

/** Item routes whose page is implemented for real (not a placeholder). */
const LIVE_ITEM_PAGES: Record<string, ReactElement> = {
  'workspace.command-center': <CommandCenterPage />,
  'workspace.market': <MarketWorkspacePage />,
  'workspace.risk': <RiskGatewayPage />,
  'workspace.positions': <PositionsPage />,
  'workspace.alerts': <PriceAlertsPage />,
  'workspace.analytics': <AnalyticsPage />,
  'workspace.assistant': <AssistantPage />,
  'research.intelligence': <IntelligencePage />,
  'research.strategy': <StrategyLabPage />,
  'research.backtest': <BacktestWorkspacePage />,
  'research.audit': <ResearchAuditPage />,
  'research.macro': <MacroIntelligencePage />,
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

        <Route
          element={
            <Suspense fallback={<RouteFallback />}>
              <Outlet />
            </Suspense>
          }
        >
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
      </Route>
    </Routes>
  )
}
