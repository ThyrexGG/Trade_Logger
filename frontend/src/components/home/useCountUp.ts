import { useEffect, useRef, useState } from 'react'

function reducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

/** Eases a number from its last shown value to `target` (ease-out cubic). Jumps straight there under reduced motion. */
export function useCountUp(target: number, durationMs = 1100, delayMs = 0): number {
  const [value, setValue] = useState(() => (reducedMotion() ? target : 0))
  const from = useRef(value)

  useEffect(() => {
    if (reducedMotion()) {
      setValue(target)
      from.current = target
      return
    }
    const start = from.current
    let raf = 0
    let t0 = 0
    const timer = window.setTimeout(() => {
      const step = (now: number) => {
        if (!t0) t0 = now
        const p = Math.min(1, (now - t0) / durationMs)
        const v = start + (target - start) * (1 - (1 - p) ** 3)
        setValue(v)
        from.current = v
        if (p < 1) raf = requestAnimationFrame(step)
      }
      raf = requestAnimationFrame(step)
    }, delayMs)
    return () => {
      window.clearTimeout(timer)
      cancelAnimationFrame(raf)
    }
  }, [target, durationMs, delayMs])

  return value
}
