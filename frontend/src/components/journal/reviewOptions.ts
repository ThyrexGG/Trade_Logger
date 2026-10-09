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
