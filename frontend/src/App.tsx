import { lazy, Suspense, type ComponentType, type ReactElement } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/shell/AppShell'
import { RouteFallback } from './components/shell/RouteFallback'
import { ALL_NAV_ITEMS, IS_FRIENDS_TIER, ZONES } from './lib/navigation'
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
const CryptoCarryPage = page(() => import('./pages/CryptoCarryPage'), 'CryptoCarryPage')
const MacroIntelligencePage = page(() => import('./pages/MacroIntelligencePage'), 'MacroIntelligencePage')
const PriceAlertsPage = page(() => import('./pages/PriceAlertsPage'), 'PriceAlertsPage')
const AnalyticsPage = page(() => import('./pages/AnalyticsPage'), 'AnalyticsPage')
const CommandCenterPage = page(() => import('./pages/CommandCenterPage'), 'CommandCenterPage')
const AssistantPage = page(() => import('./pages/AssistantPage'), 'AssistantPage')
const JournalPage = page(() => import('./pages/JournalPage'), 'JournalPage')
const SystemHealthPage = page(() => import('./pages/SystemHealthPage'), 'SystemHealthPage')
const ConnectionsPage = page(() => import('./pages/ConnectionsPage'), 'ConnectionsPage')

/** Item routes whose page is implemented for real (not a placeholder). */
const LIVE_ITEM_PAGES: Record<string, ReactElement> = {
  'workspace.command-center': <CommandCenterPage />,
  'workspace.market': <MarketWorkspacePage />,
  'workspace.risk': <RiskGatewayPage />,
  'workspace.alerts': <PriceAlertsPage />,
  'workspace.analytics': <AnalyticsPage />,
  'workspace.assistant': <AssistantPage />,
  'research.intelligence': <IntelligencePage />,
  'research.crypto-carry': <CryptoCarryPage />,
  'research.macro': <MacroIntelligencePage />,
  'operations.journal': <JournalPage />,
  'operations.system': <SystemHealthPage />,
  'operations.connections': <ConnectionsPage />,
}

/**
 * Routing foundation. All routes render inside the persistent <AppShell>.
 * Nested item routes are generated from the navigation model so future stages
 * only swap a placeholder for a real page. A zone (workspace/research/
 * evidence/operations) can be entirely absent — either because the friends
 * build filtered it out, or because every item under it was removed from
 * navigation.ts directly — so its bare zone-index route (and the default
 * landing) are resolved from `ZONES` itself rather than assumed to exist.
 */
const zoneIds = new Set(ZONES.map((z) => z.id))
const DEFAULT_LANDING = !IS_FRIENDS_TIER && zoneIds.has('workspace') ? '/workspace' : ALL_NAV_ITEMS[0]?.path ?? '/'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Navigate to={DEFAULT_LANDING} replace />} />

        <Route
          element={
            <Suspense fallback={<RouteFallback />}>
              <Outlet />
            </Suspense>
          }
        >
          <Route
            path="workspace"
            element={zoneIds.has('workspace') ? <MarketWorkspacePage /> : <Navigate to={DEFAULT_LANDING} replace />}
          />
          <Route
            path="research"
            element={zoneIds.has('research') ? <ZoneOverviewPage zoneId="research" /> : <Navigate to={DEFAULT_LANDING} replace />}
          />
          <Route
            path="evidence"
            element={zoneIds.has('evidence') ? <EvidenceCommandCenterPage /> : <Navigate to={DEFAULT_LANDING} replace />}
          />
          <Route
            path="operations"
            element={zoneIds.has('operations') ? <OperationsOverviewPage /> : <Navigate to={DEFAULT_LANDING} replace />}
          />
          {zoneIds.has('research') ? (
            <Route path="research/intelligence/asset/:symbol" element={<AssetProfilePage />} />
          ) : null}

          {ALL_NAV_ITEMS.map((item) => (
            <Route
              key={item.id}
              path={item.path.slice(1)}
              element={
                LIVE_ITEM_PAGES[item.id] ?? <PlaceholderPage itemId={item.id} />
              }
            />
          ))}

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
