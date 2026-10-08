import type { IconComponent } from './icons'
import {
  BellIcon,
  BookIcon,
  BrainIcon,
  CandlesIcon,
  ChartIcon,
  CpuIcon,
  FlaskIcon,
  GiftIcon,
  HomeIcon,
  LayersIcon,
  ReplayIcon,
  ScaleIcon,
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
        id: 'workspace.home',
        label: 'Home',
        description: 'Your trading at a glance — this month, your open trades, and a calendar of good and bad days.',
        path: '/workspace/home',
        icon: HomeIcon,
        status: 'live',
        friendsVisible: true,
      },
      {
        id: 'workspace.market',
        label: 'Market',
        description: 'Live prices and charts for the markets you follow.',
        path: '/workspace/market',
        icon: ChartIcon,
        status: 'live',
        friendsVisible: true,
      },
      {
        id: 'workspace.positions',
        label: 'Positions',
        description: 'The trades you have open right now, and how much each is up or down.',
        path: '/workspace/positions',
        icon: ReplayIcon,
        status: 'live',
        friendsVisible: true,
      },
      {
        id: 'workspace.risk',
        label: 'Risk Gateway',
        description: 'Work out how big a trade should be so a loss stays small.',
        path: '/workspace/risk',
        icon: ShieldIcon,
        status: 'live',
        friendsVisible: true,
      },
      {
        id: 'workspace.alerts',
        label: 'Price Alerts',
        description: 'Get a notification when a price reaches a level you choose.',
        path: '/workspace/alerts',
        icon: BellIcon,
        status: 'live',
      },
      {
        id: 'workspace.analytics',
        label: 'Analytics',
        description: 'How your trading is going: win rate, profit, best and worst markets.',
        path: '/workspace/analytics',
        icon: ChartIcon,
        status: 'live',
        friendsVisible: true,
      },
      {
        id: 'workspace.assistant',
        label: 'AI Assistant',
        description: 'Ask questions about your trading in plain English.',
        path: '/workspace/assistant',
        icon: BrainIcon,
        status: 'live',
      },
      {
        id: 'workspace.trade-planner',
        label: 'Trade Planner',
        description: 'Everything before a trade: find a setup, check your chart, and write your plan.',
        path: '/workspace/trade-planner',
        icon: FlaskIcon,
        status: 'live',
      },
      {
        id: 'workspace.journal',
        label: 'Journal',
        description: 'Your trading diary: every closed trade, with your notes, tags and screenshots.',
        path: '/workspace/journal',
        icon: BookIcon,
        status: 'live',
        friendsVisible: true,
      },
    ],
  },
  {
    id: 'research',
    label: 'Research & Intelligence',
    shortLabel: 'Research',
    path: '/research',
    tagline: 'Market intelligence, macro context, and the crypto funding-carry edge.',
    icon: BrainIcon,
    items: [
      {
        id: 'research.intelligence',
        label: 'Market Intelligence',
        description: 'The market’s mood and which way each market is leaning, in plain words.',
        path: '/research/intelligence',
        icon: BrainIcon,
        status: 'live',
      },
      {
        id: 'research.crypto-carry',
        label: 'Crypto Carry',
        description: 'A low-risk crypto strategy that earns a small, steady return — and how it’s doing.',
        path: '/research/crypto-carry',
        icon: ScaleIcon,
        status: 'live',
      },
      {
        id: 'research.macro',
        label: 'Macro Intelligence',
        description: 'Economic news that moves prices: upcoming events and recent surprises.',
        path: '/research/macro',
        icon: BrainIcon,
        status: 'live',
      },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    shortLabel: 'Operations',
    path: '/operations',
    tagline: 'System health, broker connections and partners.',
    icon: LayersIcon,
    items: [
      {
        id: 'operations.system',
        label: 'System Health',
        description: 'Check that everything behind the app is working.',
        path: '/operations/system',
        icon: CpuIcon,
        status: 'live',
      },
      {
        id: 'operations.connections',
        label: 'Connections',
        description: 'Connect your broker so trades come in automatically.',
        path: '/operations/connections',
        icon: ShieldIcon,
        status: 'live',
        friendsVisible: true,
      },
      {
        id: 'operations.partners',
        label: 'Partners',
        description: "Brokers and prop firms we vouch for — some are referral links.",
        path: '/operations/partners',
        icon: GiftIcon,
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
