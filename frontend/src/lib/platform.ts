/** True when running on macOS — used to show ⌘ vs Ctrl in shortcut hints. */
export function isMac(): boolean {
  if (typeof navigator === 'undefined') return false
  return /mac|iphone|ipad|ipod/i.test(navigator.platform || navigator.userAgent)
}
