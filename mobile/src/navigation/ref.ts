import { createNavigationContainerRef } from '@react-navigation/native'
import type { RootStackParamList } from './RootStack'

export const navigationRef = createNavigationContainerRef<RootStackParamList>()

interface Target {
  kind: string
  refId: string
}

// A notification tapped while the app was closed arrives before the navigator exists.
let pending: Target | null = null

function go(t: Target): void {
  if (t.kind === 'opened') navigationRef.navigate('PositionDetail', { positionId: t.refId })
  else if (t.kind === 'closed') navigationRef.navigate('TradeDetail', { tradeId: t.refId })
}

/** Open the trade a push notification is about. `data` is the payload the server attached. */
export function openFromNotification(data: unknown): void {
  const d = (data ?? {}) as { kind?: unknown; ref_id?: unknown }
  if (typeof d.kind !== 'string' || typeof d.ref_id !== 'string' || !d.ref_id) return
  const target = { kind: d.kind, refId: d.ref_id }
  if (navigationRef.isReady()) go(target)
  else pending = target
}

/** Call from NavigationContainer's onReady to deliver a tap that happened before it existed. */
export function flushPendingNavigation(): void {
  if (pending && navigationRef.isReady()) {
    const t = pending
    pending = null
    go(t)
  }
}
