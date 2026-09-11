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
  /** Visible in the stripped-down "friends" build (see IS_FRIENDS_TIER below).
   * Unset/false = hidden there; always visible in the full (local/owner) build. */
  friendsVisible?: boolean
}

/**
 * Two builds share this one codebase: the full app (local dev, the owner) and
 * a stripped-down "friends" build for the online deploy, toggled by a
 * build-time env flag — no second deployment, no second copy of the code.
 * Every consumer of ZONES/ALL_NAV_ITEMS below (sidebar, breadcrumbs, bottom
 * nav, zone overview pages, and App.tsx's route generation) reads the
 * already-filtered list, so a hidden page has no route at all in that build.
 */
export const IS_FRIENDS_TIER = import.meta.env.VITE_APP_TIER === 'friends'

export interface Zone {
  id: string
  label: string
  shortLabel: string
  path: string
  tagline: string
  icon: IconComponent
  items: NavItem[]
}

const ALL_ZONES: Zone[] = [
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
        id: 'workspace.trade-setup',
        label: 'Trade Setup',
        description: 'Does the current market satisfy a validated strategy right now? READY only behind a validated edge.',
        path: '/workspace/trade-setup',
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
        friendsVisible: true,
      },
      {
        id: 'workspace.alerts',
        label: 'Price Alerts',
        description: 'Price-target alerts (notification only, no orders).',
        path: '/workspace/alerts',
        icon: BellIcon,
        status: 'live',
        friendsVisible: true,
      },
      {
        id: 'workspace.analytics',
        label: 'Analytics',
        description: 'Filtered trading performance over the closed-trade journal.',
        path: '/workspace/analytics',
        icon: ChartIcon,
        status: 'live',
        friendsVisible: true,
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
        id: 'research.discovery',
        label: 'Strategy Discovery',
        description: 'Pair × strategy leaderboard, robustness and the recovered Gold baseline.',
        path: '/research/discovery',
        icon: FlaskIcon,
        status: 'live',
      },
      {
        id: 'research.backtest',
        label: 'Backtest & Edge Audit',
        description: 'One config, two analyses: historical backtest (walk-forward, Monte Carlo) and statistical edge / adversarial audit (R-multiples, bootstrap, stress).',
        path: '/research/backtest',
        icon: ReplayIcon,
        status: 'live',
      },
      {
        id: 'research.crypto-carry',
        label: 'Crypto Carry',
        description: 'Delta-neutral crypto funding carry — the one usable edge: recommended book, sizing, and the weekly forward-evidence tracker.',
        path: '/research/crypto-carry',
        icon: ScaleIcon,
        status: 'live',
      },
      {
        id: 'research.macro',
        label: 'Macro Intelligence',
        description: 'Economic calendar, surprise, currency strength and asset macro context.',
        path: '/research/macro',
        icon: BrainIcon,
        status: 'live',
      },
    ],
  },
  {
    id: 'evidence',
    label: 'Forward Evidence & Governance',
    shortLabel: 'Evidence',
    path: '/evidence',
    tagline: 'Live-vs-backtest forward tracking for every edge, plus statistical surveillance and governance.',
    icon: GaugeIcon,
    items: [
      {
        id: 'evidence.forward',
        label: 'XAUUSD Forward',
        description: 'Forward sample accumulation and decision state for the frozen XAUUSD directional contract (Phase 49).',
        path: '/evidence/forward',
        icon: GaugeIcon,
        status: 'live',
      },
      {
        id: 'evidence.statistics',
        label: 'Statistics',
        description: 'Statistical surveillance, milestones and holdout comparison for the XAUUSD contract.',
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
        friendsVisible: true,
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
      {
        id: 'operations.connections',
        label: 'Connections',
        description: 'Your broker connection — credentials encrypted at rest.',
        path: '/operations/connections',
        icon: ShieldIcon,
        status: 'live',
        friendsVisible: true,
      },
    ],
  },
]

/** The friends build only ever sees `friendsVisible` items; empty zones drop out. */
function forFriends(zones: Zone[]): Zone[] {
  return zones
    .map((zone) => ({ ...zone, items: zone.items.filter((item) => item.friendsVisible) }))
    .filter((zone) => zone.items.length > 0)
}

export const ZONES: Zone[] = IS_FRIENDS_TIER ? forFriends(ALL_ZONES) : ALL_ZONES

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
