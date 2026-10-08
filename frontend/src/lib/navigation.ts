import type { IconComponent } from './icons'
import {
  BellIcon,
  BookIcon,
  BrainIcon,
  ChartIcon,
  CpuIcon,
  FlaskIcon,
  GearIcon,
  GiftIcon,
  HomeIcon,
  ReplayIcon,
  ScaleIcon,
  ShieldIcon,
  TargetIcon,
} from './icons'

/**
 * Declarative product information architecture, organised around a trader's
 * day — Today, Plan, Review, Learn — plus Settings. Zones are groups for the
 * sidebar, bottom bar and breadcrumbs; every item keeps its original URL, so
 * links, bookmarks and deep links (e.g. /workspace/journal?trade=…) are
 * unchanged by the regrouping.
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
    id: 'today',
    label: 'Today',
    shortLabel: 'Today',
    path: '/workspace/home',
    tagline: 'What is happening with your trading right now.',
    icon: HomeIcon,
    items: [
      {
        id: 'workspace.home',
        label: 'Overview',
        description: 'Your trading at a glance — this month, your open trades, and a calendar of good and bad days.',
        path: '/workspace/home',
        icon: HomeIcon,
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
        id: 'workspace.alerts',
        label: 'Price Alerts',
        description: 'Get a notification when a price reaches a level you choose.',
        path: '/workspace/alerts',
        icon: BellIcon,
        status: 'live',
      },
    ],
  },
  {
    id: 'plan',
    label: 'Plan',
    shortLabel: 'Plan',
    path: '/workspace/trade-planner',
    tagline: 'Everything before you place a trade.',
    icon: TargetIcon,
    items: [
      {
        id: 'workspace.trade-planner',
        label: 'Trade Planner',
        description: 'Everything before a trade: find a setup, check your chart, and write your plan.',
        path: '/workspace/trade-planner',
        icon: FlaskIcon,
        status: 'live',
      },
      {
        id: 'workspace.risk',
        label: 'Position Size',
        description: 'Work out how big a trade should be so a loss stays small.',
        path: '/workspace/risk',
        icon: ShieldIcon,
        status: 'live',
        friendsVisible: true,
      },
      {
        id: 'workspace.market',
        label: 'Charts',
        description: 'Live prices and charts for the markets you follow.',
        path: '/workspace/market',
        icon: ChartIcon,
        status: 'live',
        friendsVisible: true,
      },
    ],
  },
  {
    id: 'review',
    label: 'Review',
    shortLabel: 'Review',
    path: '/workspace/journal',
    tagline: 'Look back at your trades and learn from them.',
    icon: BookIcon,
    items: [
      {
        id: 'workspace.journal',
        label: 'Journal',
        description: 'Your trading diary: every closed trade, with your notes, tags and screenshots.',
        path: '/workspace/journal',
        icon: BookIcon,
        status: 'live',
        friendsVisible: true,
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
        label: 'Ask AI',
        description: 'Ask questions about your trading in plain English.',
        path: '/workspace/assistant',
        icon: BrainIcon,
        status: 'live',
      },
    ],
  },
  {
    id: 'learn',
    label: 'Learn',
    shortLabel: 'Learn',
    path: '/research/intelligence',
    tagline: 'Understand what is moving the markets.',
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
        id: 'research.macro',
        label: 'Economic News',
        description: 'Economic news that moves prices: upcoming events and recent surprises.',
        path: '/research/macro',
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
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    shortLabel: 'Settings',
    path: '/operations/connections',
    tagline: 'Your broker connection and the app itself.',
    icon: GearIcon,
    items: [
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
        id: 'operations.system',
        label: 'System Health',
        description: 'Check that everything behind the app is working.',
        path: '/operations/system',
        icon: CpuIcon,
        status: 'live',
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
  return (
    ZONES.find((zone) => zone.items.some((item) => pathname === item.path)) ??
    ZONES.find((zone) => zone.items.some((item) => pathname.startsWith(`${item.path}/`)))
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
  if (item && item.path !== zone.path) {
    crumbs.push({ label: item.label, path: item.path })
  } else if (item) {
    crumbs[0] = { label: zone.shortLabel, path: zone.path }
    if (item.label !== zone.shortLabel) crumbs.push({ label: item.label, path: item.path })
  }

  // Asset intelligence detail: /research/intelligence/asset/:symbol
  const assetMatch = pathname.match(/^\/research\/intelligence\/asset\/([^/]+)$/)
  if (assetMatch) {
    const intel = ALL_NAV_ITEMS.find((i) => i.id === 'research.intelligence')
    if (intel && !crumbs.some((c) => c.path === intel.path)) crumbs.push({ label: intel.label, path: intel.path })
    crumbs.push({
      label: decodeURIComponent(assetMatch[1]).toUpperCase(),
      path: pathname,
    })
  }

  return crumbs
}
