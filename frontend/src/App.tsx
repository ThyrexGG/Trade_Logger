import type { ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/shell/AppShell'
import { ALL_NAV_ITEMS } from './lib/navigation'
import { MarketWorkspacePage } from './pages/MarketWorkspacePage'
import { RiskGatewayPage } from './pages/RiskGatewayPage'
import { ZoneOverviewPage } from './pages/ZoneOverviewPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { SystemHealthPage } from './pages/SystemHealthPage'
import { NotFoundPage } from './pages/NotFoundPage'

/** Item routes whose page is implemented for real (not a placeholder). */
const LIVE_ITEM_PAGES: Record<string, ReactElement> = {
  'workspace.market': <MarketWorkspacePage />,
  'workspace.risk': <RiskGatewayPage />,
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
        <Route path="evidence" element={<ZoneOverviewPage zoneId="evidence" />} />
        <Route
          path="operations"
          element={<ZoneOverviewPage zoneId="operations" />}
        />

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
    </Routes>
  )
}
