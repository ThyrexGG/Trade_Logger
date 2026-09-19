export const MIN_SCALE = 1
export const MAX_SCALE = 5
export const DOUBLE_TAP_SCALE = 2.5

export const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v))

/** Distance between two touch points. */
export function distance(a: { pageX: number; pageY: number }, b: { pageX: number; pageY: number }): number {
  return Math.hypot(a.pageX - b.pageX, a.pageY - b.pageY)
}

/** New scale while pinching: the ratio of finger distances applied to the scale the pinch started at. */
export function pinchScale(startScale: number, startDistance: number, currentDistance: number): number {
  if (startDistance <= 0) return startScale
  return clamp(startScale * (currentDistance / startDistance), MIN_SCALE, MAX_SCALE)
}

/** Keep a zoomed image from being dragged off-screen: at scale s the overflow on each side is (s-1)*size/2. */
export function clampTranslate(t: number, scale: number, size: number): number {
  const limit = ((scale - 1) * size) / 2
  return clamp(t, -limit, limit)
}

/** Double-tap toggles between fit-to-screen and a comfortable zoom. */
export function doubleTapTarget(currentScale: number): number {
  return currentScale > 1.05 ? MIN_SCALE : DOUBLE_TAP_SCALE
}
