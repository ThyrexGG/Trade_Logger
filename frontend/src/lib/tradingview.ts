/**
 * Resolve a chart-snapshot URL to something an <img> can render.
 *
 * TradingView "snapshot" share links look like
 *   https://www.tradingview.com/x/aBcDeFgH/
 * and the underlying PNG lives at
 *   https://s3.tradingview.com/snapshots/<first-char-lowercased>/aBcDeFgH.png
 *
 * A direct image URL (any host) is returned as-is. Anything else -> null, and
 * the caller falls back to a plain link.
 */
const TV_SHARE_RE = /tradingview\.com\/x\/([A-Za-z0-9]+)/i
const IMAGE_RE = /\.(png|jpe?g|webp|gif)(\?|#|$)/i

export function resolveChartImage(raw: string | null | undefined): string | null {
  const url = (raw ?? '').trim()
  if (!url) return null

  const share = url.match(TV_SHARE_RE)
  if (share) {
    const id = share[1]
    return `https://s3.tradingview.com/snapshots/${id[0].toLowerCase()}/${id}.png`
  }

  if (IMAGE_RE.test(url)) return url
  return null
}

/** True when the value is a URL we can at least open in a new tab. */
export function isLinkable(raw: string | null | undefined): boolean {
  const url = (raw ?? '').trim()
  return /^https?:\/\//i.test(url)
}
