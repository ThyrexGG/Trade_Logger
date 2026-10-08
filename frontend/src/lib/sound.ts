/**
 * Tiny UI sounds — a soft "plop" when you press a button, link or tab.
 * Synthesised with the Web Audio API (no audio files to download), very
 * quiet, and switchable from the account menu (remembered per device).
 *
 * One delegated listener covers the whole app, so no component has to opt
 * in. An element (or any ancestor) with `data-silent` never plays, and text
 * fields never do.
 */
import { useSyncExternalStore } from 'react'

const KEY = 'tl.sound'
const listeners = new Set<() => void>()
let ctx: AudioContext | null = null
let lastAt = 0

function read(): boolean {
  try {
    return localStorage.getItem(KEY) !== 'off'
  } catch {
    return true
  }
}

let enabled = read()

export function soundEnabled(): boolean {
  return enabled
}

export function setSoundEnabled(on: boolean): void {
  enabled = on
  try {
    localStorage.setItem(KEY, on ? 'on' : 'off')
  } catch {
    /* per-device convenience only */
  }
  listeners.forEach((l) => l())
  if (on) play('bubble')
}

export function useSoundEnabled(): boolean {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => enabled,
    () => true,
  )
}

type Kind = 'plop' | 'bubble' | 'chime'

export function play(kind: Kind = 'plop'): void {
  if (!enabled) return
  const now = performance.now()
  if (now - lastAt < 45) return // a double-fire from one press shouldn't stutter
  lastAt = now
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctx) return
    ctx = ctx ?? new Ctx()
    if (ctx.state === 'suspended') void ctx.resume()
    const notes: [number, number][] =
      kind === 'chime' ? [[660, 0], [880, 0.08], [1320, 0.16]] : kind === 'bubble' ? [[520, 0], [780, 0.06]] : [[600, 0]]
    for (const [freq, offset] of notes) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      const at = ctx.currentTime + offset
      osc.type = 'sine'
      osc.frequency.setValueAtTime(freq, at)
      if (kind !== 'chime') osc.frequency.exponentialRampToValueAtTime(freq * 0.5, at + 0.1)
      gain.gain.setValueAtTime(0.0001, at)
      gain.gain.exponentialRampToValueAtTime(kind === 'chime' ? 0.07 : 0.05, at + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.0001, at + (kind === 'chime' ? 0.35 : 0.13))
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(at)
      osc.stop(at + 0.4)
    }
  } catch {
    /* audio unavailable — silently skip */
  }
}

const PRESSABLE = 'button, a[href], [role="tab"], [role="radio"], [role="menuitem"], summary'

/** Call once at startup. Returns a cleanup for tests/HMR. */
export function installClickSounds(): () => void {
  const onDown = (e: PointerEvent) => {
    if (!enabled || e.button !== 0) return
    const target = e.target as Element | null
    if (!target || target.closest('input, textarea, select, [contenteditable="true"], [data-silent]')) return
    const el = target.closest(PRESSABLE) as HTMLButtonElement | null
    if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true') return
    play('plop')
  }
  document.addEventListener('pointerdown', onDown, { capture: true, passive: true })
  return () => document.removeEventListener('pointerdown', onDown, { capture: true })
}
