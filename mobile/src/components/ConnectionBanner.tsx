import { useHealth } from '../HealthContext'
import { Notice } from './ui'

/** Shown only when the server can't be reached — tells the user the screen is showing saved data. */
export function ConnectionBanner() {
  const { state, recheck } = useHealth()
  if (state !== 'unreachable') return null
  return <Notice onPress={recheck}>Can't reach the server. Showing the last data we loaded. Tap to retry.</Notice>
}
