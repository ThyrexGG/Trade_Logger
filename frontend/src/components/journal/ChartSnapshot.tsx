import { useState } from 'react'
import { isLinkable, resolveChartImage } from '../../lib/tradingview'

/**
 * Renders a chart-snapshot URL (a TradingView `/x/…` share link or any direct
 * image URL) as an inline thumbnail that opens fullscreen on click. Falls back
 * to a plain "open ↗" link when the URL isn't an image or the image fails to
 * load (private / expired snapshot).
 */
export function ChartSnapshot({
  url,
  compact = false,
}: {
  url: string | null | undefined
  compact?: boolean
}) {
  const [full, setFull] = useState(false)
  const [broken, setBroken] = useState(false)
  const img = resolveChartImage(url)
  const link = (url ?? '').trim()

  if (!link) return null

  if (!img || broken) {
    return isLinkable(link) ? (
      <a
        href={link}
        target="_blank"
        rel="noreferrer"
        className="text-[10px] text-accent hover:underline"
      >
        chart ↗
      </a>
    ) : null
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setFull(true)}
        className={`block overflow-hidden rounded border border-border hover:border-accent ${
          compact ? 'h-14 w-24' : 'h-32 w-full max-w-xs'
        }`}
        title="Open chart snapshot"
      >
        <img
          src={img}
          alt="chart snapshot"
          loading="lazy"
          onError={() => setBroken(true)}
          className="h-full w-full object-cover"
        />
      </button>

      {full ? (
        <div
          className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4"
          onClick={() => setFull(false)}
        >
          <div className="max-h-full max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <img src={img} alt="chart snapshot" className="max-h-[80vh] w-auto rounded" />
            <div className="mt-2 flex items-center justify-between text-[11px] text-white/80">
              <a href={link} target="_blank" rel="noreferrer" className="hover:underline">
                open original ↗
              </a>
              <button type="button" onClick={() => setFull(false)} className="hover:text-white">
                close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
