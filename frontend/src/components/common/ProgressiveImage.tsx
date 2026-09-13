import { useState, type ImgHTMLAttributes } from 'react'

/**
 * An `<img>` that shows a shimmering skeleton in its place until the real
 * bytes arrive, then cross-fades in — instead of a blank box or a layout
 * jump. These images (trade screenshots, chart snapshots) are each a
 * separate network request, not bundled data, so there's a genuine loading
 * window worth covering. No low-res placeholder is generated server-side,
 * so this is a fade-up rather than a true blur-up — an honest middle
 * ground that needs no backend change and still kills the blank-box flash.
 */
export function ProgressiveImage({
  className = '',
  onError,
  ...imgProps
}: ImgHTMLAttributes<HTMLImageElement>) {
  const [loaded, setLoaded] = useState(false)

  return (
    <span className="relative block h-full w-full overflow-hidden">
      {!loaded ? (
        <span className="absolute inset-0 animate-pulse bg-surface-elevated" aria-hidden="true" />
      ) : null}
      {/* eslint-disable-next-line jsx-a11y/alt-text -- alt comes through ...imgProps */}
      <img
        {...imgProps}
        onLoad={(e) => {
          setLoaded(true)
          imgProps.onLoad?.(e)
        }}
        onError={(e) => {
          // Nothing is coming — drop the skeleton so a broken-image icon (or
          // the caller's own onError fallback) isn't hidden underneath it.
          setLoaded(true)
          onError?.(e)
        }}
        className={`${className} transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
      />
    </span>
  )
}
