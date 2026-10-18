/**
 * Privacy mode — hides dollar amounts everywhere (balances, P&L, best/worst
 * day…) so a screen can be shared or recorded. Percentages, win rates and
 * trade counts stay visible, and so does the +/- sign and green/red colour,
 * so the shape of your results still reads.
 *
 * It works at the one choke point every money figure goes through:
 * `formatUsd` in lib/format.ts (and `formatSignedAmount`, built on it).
 * Switchable from the account menu and the Analytics header; remembered per
 * device, like click sounds.
 */
import { useSyncExternalStore } from 'react'

const KEY = 'tl.privacy'
const listeners = new Set<() => void>()

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === 'on'
  } catch {
    return false
  }
}

let hidden = read()

export function amountsHidden(): boolean {
  return hidden
}

export function setAmountsHidden(on: boolean): void {
  hidden = on
  try {
    localStorage.setItem(KEY, on ? 'on' : 'off')
  } catch {
    /* per-device convenience only */
  }
  listeners.forEach((l) => l())
}

export function useAmountsHidden(): boolean {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => hidden,
    () => false,
  )
}

/** What a hidden amount shows instead of digits. */
export const HIDDEN_AMOUNT = '•••'
