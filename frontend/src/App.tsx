import { lazy, Suspense, type ComponentType, type ReactElement } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/shell/AppShell'
import { RouteFallback } from './components/shell/RouteFallback'
import { ALL_NAV_ITEMS, IS_FRIENDS_TIER, ZONES } from './lib/navigation'
// The default landing view and the lightweight zone/overview pages stay in the
// main bundle so the first paint after load needs no extra round-trip.
import { MarketWorkspacePage } from './pages/MarketWorkspacePage'
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

const PositionsPage = page(() => import('./pages/PositionsPage'), 'PositionsPage')
const RiskGatewayPage = page(() => import('./pages/RiskGatewayPage'), 'RiskGatewayPage')
const IntelligencePage = page(() => import('./pages/IntelligencePage'), 'IntelligencePage')
const AssetProfilePage = page(() => import('./pages/AssetProfilePage'), 'AssetProfilePage')
const CryptoCarryPage = page(() => import('./pages/CryptoCarryPage'), 'CryptoCarryPage')
const MacroIntelligencePage = page(() => import('./pages/MacroIntelligencePage'), 'MacroIntelligencePage')
const PriceAlertsPage = page(() => import('./pages/PriceAlertsPage'), 'PriceAlertsPage')
const AnalyticsPage = page(() => import('./pages/AnalyticsPage'), 'AnalyticsPage')
const AssistantPage = page(() => import('./pages/AssistantPage'), 'AssistantPage')
const TradePlannerPage = page(() => import('./pages/TradePlannerPage'), 'TradePlannerPage')
const JournalPage = page(() => import('./pages/JournalPage'), 'JournalPage')
const SystemHealthPage = page(() => import('./pages/SystemHealthPage'), 'SystemHealthPage')
const ConnectionsPage = page(() => import('./pages/ConnectionsPage'), 'ConnectionsPage')
const PartnersPage = page(() => import('./pages/PartnersPage'), 'PartnersPage')
const HomePage = page(() => import('./pages/HomePage'), 'HomePage')

/** Item routes whose page is implemented for real (not a placeholder). */
const LIVE_ITEM_PAGES: Record<string, ReactElement> = {
  'workspace.home': <HomePage />,
  'workspace.market': <MarketWorkspacePage />,
  'workspace.positions': <PositionsPage />,
  'workspace.risk': <RiskGatewayPage />,
  'workspace.alerts': <PriceAlertsPage />,
  'workspace.analytics': <AnalyticsPage />,
  'workspace.assistant': <AssistantPage />,
  'workspace.trade-planner': <TradePlannerPage />,
  'workspace.journal': <JournalPage />,
  'research.intelligence': <IntelligencePage />,
  'research.crypto-carry': <CryptoCarryPage />,
  'research.macro': <MacroIntelligencePage />,
  'operations.system': <SystemHealthPage />,
  'operations.connections': <ConnectionsPage />,
  'operations.partners': <PartnersPage />,
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
// Home is the first screen after sign-in in both builds; fall back to the old
// landing only if it's ever removed from navigation.
const HOME_PATH = ALL_NAV_ITEMS.find((i) => i.id === 'workspace.home')?.path
const DEFAULT_LANDING = HOME_PATH ?? (!IS_FRIENDS_TIER && zoneIds.has('workspace') ? '/workspace' : ALL_NAV_ITEMS[0]?.path ?? '/')

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
            element={
              // The logo, the "Workspace" breadcrumb and the phone's Workspace
              // tab all land here — send them Home like a fresh launch does.
              // Market stays at /workspace/market.
              HOME_PATH ? (
                <Navigate to={HOME_PATH} replace />
              ) : zoneIds.has('workspace') ? (
                <MarketWorkspacePage />
              ) : (
                <Navigate to={DEFAULT_LANDING} replace />
              )
            }
          />
          <Route
            path="research"
            element={<Navigate to="/research/intelligence" replace />}
          />
          <Route
            path="evidence"
            element={zoneIds.has('evidence') ? <EvidenceCommandCenterPage /> : <Navigate to={DEFAULT_LANDING} replace />}
          />
          <Route
            path="operations"
            element={<Navigate to="/operations/connections" replace />}
          />
          {/* Command Center was folded into Home — keep old links/bookmarks working. */}
          <Route path="workspace/command-center" element={<Navigate to={DEFAULT_LANDING} replace />} />
          <Route path="workspace/loss-limits" element={<Navigate to={DEFAULT_LANDING} replace />} />
          {/* Killzone Scanner + Chart Analyzer became the Trade Planner's tabs. */}
          <Route path="workspace/killzone-scanner" element={<Navigate to="/workspace/trade-planner" replace />} />
          <Route path="workspace/chart-analyzer" element={<Navigate to="/workspace/trade-planner?tab=chart" replace />} />
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
