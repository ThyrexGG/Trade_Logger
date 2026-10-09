import type { ExitReason, StopPlacement } from '../../types/operations'

/** Plain-English labels for the per-trade review answers (codes match the API). */
export const STOP_PLACEMENTS: { value: StopPlacement; label: string }[] = [
  { value: 'sweep', label: 'Beyond the sweep high/low' },
  { value: 'second', label: 'Beyond the 2nd high/low (pullback)' },
  { value: 'fvg', label: 'Beyond the gap (FVG)' },
  { value: 'structure', label: 'Beyond another swing point' },
  { value: 'fixed', label: 'Fixed points / pips' },
  { value: 'other', label: 'Other' },
]

export const EXIT_REASONS: { value: ExitReason; label: string }[] = [
  { value: 'target', label: 'Hit my target' },
  { value: 'partial_runner', label: 'Took a partial, then closed the rest' },
  { value: 'stopped', label: 'Stopped out' },
  { value: 'breakeven', label: 'Stopped at breakeven' },
  { value: 'cut_early', label: 'Closed early by hand' },
  { value: 'time', label: 'Out of time (end of my window)' },
  { value: 'other', label: 'Other' },
]

/**
 * The ONE tap per trade. Stored as the trade's setup tag, so the existing tag record ("which kind of trade pays") works with no new plumbing.
 * Wording is the user's own rule: no blind or rushed entries.
 */
export const QUICK_TAGS: { value: string; label: string; hint: string }[] = [
  { value: 'By my rules', label: 'By my rules', hint: 'I waited for my confirmation and followed my plan' },
  { value: 'Bent my rules', label: 'Bent my rules', hint: 'Mostly my plan, but I changed something' },
  { value: 'Rushed', label: 'Rushed / off-plan', hint: 'I jumped in without my confirmation' },
]
