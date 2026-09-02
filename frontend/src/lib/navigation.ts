import type { IconComponent } from './icons'
import {
  BellIcon,
  BookIcon,
  BrainIcon,
  CandlesIcon,
  ChartIcon,
  CpuIcon,
  FlaskIcon,
  GaugeIcon,
  LayersIcon,
  ReplayIcon,
  ScaleIcon,
  SearchIcon,
  ShieldIcon,
} from './icons'

/**
 * Declarative product information architecture.
 *
 * This is the single source of truth for the sidebar, breadcrumbs and command
 * palette. Future stages add pages by flipping `status` to 'live' and pointing
 * a route at a real component — no navigation logic is duplicated elsewhere.
 */

export type PageStatus = 'live' | 'shell'

export interface NavItem {
  id: string
  label: string
  description: string
  path: string
  icon: IconComponent
  status: PageStatus
}

export interface Zone {
  id: string
  label: string
  shortLabel: string
  path: string
  tagline: string
  icon: IconComponent
  items: NavItem[]
}

export const ZONES: Zone[] = [
  {
    id: 'workspace',
    label: 'Trading Workspace',
    shortLabel: 'Workspace',
    path: '/workspace',
    tagline: 'Primary market monitoring and trading workspace.',
    icon: CandlesIcon,
    items: [
      {
        id: 'workspace.command-center',
        label: 'Command Center',
        description: 'Daily "what matters today" overview — read-only aggregate.',
        path: '/workspace/command-center',
        icon: GaugeIcon,
        status: 'live',
      },
      {
        id: 'workspace.market',
        label: 'Market',
        description: 'Watchlist, market snapshot and multi-timeframe context.',
        path: '/workspace/market',
        icon: ChartIcon,
        status: 'live',
      },
      {
        id: 'workspace.risk',
        label: 'Risk Gateway',
        description: 'Position sizing and risk preview (calculation only).',
        path: '/workspace/risk',
        icon: ShieldIcon,
        status: 'live',
      },
      {
        id: 'workspace.positions',
        label: 'Positions',
        description: 'Open paper/shadow positions and excursion metrics.',
        path: '/workspace/positions',
        icon: ScaleIcon,
        status: 'live',
      },
      {
        id: 'workspace.alerts',
        label: 'Price Alerts',
        description: 'Price-target alerts (notification only, no orders).',
        path: '/workspace/alerts',
        icon: BellIcon,
        status: 'live',
      },
      {
        id: 'workspace.analytics',
        label: 'Analytics',
        description: 'Filtered trading performance over the closed-trade journal.',
        path: '/workspace/analytics',
        icon: ChartIcon,
        status: 'live',
      },
      {
        id: 'workspace.assistant',
        label: 'AI Assistant',
        description: 'Read-only analytical chat over your TradeLogger data.',
        path: '/workspace/assistant',
        icon: BrainIcon,
        status: 'live',
      },
    ],
  },
  {
    id: 'research',
    label: 'Research & Strategy Lab',
    shortLabel: 'Research',
    path: '/research',
    tagline: 'Research, strategy development and market intelligence.',
    icon: BrainIcon,
    items: [
      {
        id: 'research.intelligence',
        label: 'Market Intelligence',
        description: 'Cross-asset regime, breadth and macro intelligence.',
        path: '/research/intelligence',
        icon: BrainIcon,
        status: 'live',
      },
      {
        id: 'research.strategy',
        label: 'Strategy Lab',
        description: 'Frozen strategy contract, research config and methodology.',
        path: '/research/strategy',
        icon: FlaskIcon,
        status: 'live',
      },
      {
        id: 'research.backtest',
        label: 'Backtesting',
        description: 'Historical research backtests, walk-forward and Monte Carlo.',
        path: '/research/backtest',
        icon: ReplayIcon,
        status: 'live',
      },
      {
        id: 'research.audit',
        label: 'Edge Audit',
        description: 'Statistical edge & adversarial audit (R-multiples, bootstrap, stress).',
        path: '/research/audit',
        icon: FlaskIcon,
        status: 'live',
      },
    ],
  },
  {
    id: 'evidence',
    label: 'Forward Evidence & Governance',
    shortLabel: 'Evidence',
    path: '/evidence',
    tagline: 'Statistical validation, forward evidence and governance.',
    icon: GaugeIcon,
    items: [
      {
        id: 'evidence.forward',
        label: 'Forward Evidence',
        description: 'Forward sample accumulation and decision state.',
        path: '/evidence/forward',
        icon: GaugeIcon,
        status: 'live',
      },
      {
        id: 'evidence.statistics',
        label: 'Statistics',
        description: 'Statistical surveillance, milestones and holdout comparison.',
        path: '/evidence/statistics',
        icon: ChartIcon,
        status: 'live',
      },
      {
        id: 'evidence.governance',
        label: 'Governance',
        description: 'Governance state and evidence provenance.',
        path: '/evidence/governance',
        icon: ShieldIcon,
        status: 'live',
      },
    ],
  },
  {
    id: 'operations',
    label: 'Operations, Journal & Audit',
    shortLabel: 'Operations',
    path: '/operations',
    tagline: 'Operational visibility and trading records.',
    icon: LayersIcon,
    items: [
      {
        id: 'operations.journal',
        label: 'Journal',
        description: 'Closed-trade journal with setup tags, notes and ratings.',
        path: '/operations/journal',
        icon: BookIcon,
        status: 'live',
      },
      {
        id: 'operations.audit',
        label: 'Audit',
        description: 'Operational execution audit trail (read-only).',
        path: '/operations/audit',
        icon: SearchIcon,
        status: 'live',
      },
      {
        id: 'operations.system',
        label: 'System Health',
        description: 'Backend service health, performance and configuration.',
        path: '/operations/system',
        icon: CpuIcon,
        status: 'live',
      },
    ],
  },
]

export const ALL_NAV_ITEMS: NavItem[] = ZONES.flatMap((zone) => zone.items)

export function findZoneByPath(pathname: string): Zone | undefined {
  return ZONES.find(
    (zone) => pathname === zone.path || pathname.startsWith(`${zone.path}/`),
  )
}

export function findItemByPath(pathname: string): NavItem | undefined {
  return ALL_NAV_ITEMS.find((item) => item.path === pathname)
}

export interface Crumb {
  label: string
  path: string
}

/** Derives breadcrumb trail from the current route, e.g. Research / Intelligence. */
export function getBreadcrumbs(pathname: string): Crumb[] {
  const zone = findZoneByPath(pathname)
  if (!zone) return []

  const crumbs: Crumb[] = [{ label: zone.shortLabel, path: zone.path }]
  const item = findItemByPath(pathname)
  if (item) {
    crumbs.push({ label: item.label, path: item.path })
  }

  // Asset intelligence detail: /research/intelligence/asset/:symbol
  const assetMatch = pathname.match(/^\/research\/intelligence\/asset\/([^/]+)$/)
  if (assetMatch) {
    const intel = ALL_NAV_ITEMS.find((i) => i.id === 'research.intelligence')
    if (intel) crumbs.push({ label: intel.label, path: intel.path })
    crumbs.push({
      label: decodeURIComponent(assetMatch[1]).toUpperCase(),
      path: pathname,
    })
  }

  return crumbs
}
