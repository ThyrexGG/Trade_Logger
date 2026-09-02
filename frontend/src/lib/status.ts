import type { StatusTone } from '../components/shell/StatusDot'
import type { ConnectionState } from './health'

interface StatusView {
  tone: StatusTone
  label: string
  pulse: boolean
}

/** Maps the shared health connection state to API / system indicator views. */
export function apiStatusView(state: ConnectionState): StatusView {
  switch (state) {
    case 'connected':
      return { tone: 'positive', label: 'Connected', pulse: false }
    case 'error':
      return { tone: 'negative', label: 'Unreachable', pulse: false }
    case 'loading':
    default:
      return { tone: 'warning', label: 'Checking', pulse: true }
  }
}

export function systemStatusView(state: ConnectionState): StatusView {
  switch (state) {
    case 'connected':
      return { tone: 'positive', label: 'Operational', pulse: false }
    case 'error':
      return { tone: 'warning', label: 'Degraded', pulse: false }
    case 'loading':
    default:
      return { tone: 'neutral', label: 'Unknown', pulse: true }
  }
}
