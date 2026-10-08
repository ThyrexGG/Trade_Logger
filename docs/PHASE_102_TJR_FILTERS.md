# Phase 102: TJR's filters on the NY-open sweep (SMT divergence, daily bias, liquidity targets)

Run 2026-10-08. Code: [`phase102_tjr_filters.py`](../phase102_tjr_filters.py)
(`python -m phase102_tjr_filters`); it reuses Phase 101's data, levels, entries
and exit simulator unchanged ([PHASE_101_NY_OPEN_SWEEP.md](PHASE_101_NY_OPEN_SWEEP.md)).

## Verdict

**`NO_EDGE`.** Adding TJR's own confirmations didn't help, and mostly made
results worse.

- **SMT divergence** (one index sweeps, the other refuses) took about a third
  of the trades away, but the remaining trades did no better.
- **Daily bias** made the simple entry clearly *worse* (NQ −0.11R → −0.25R,
  ES −0.14R → −0.23R per trade): fading sweeps in the direction of the daily
  trend lost more. Flipping it now (trading against the trend) would be a
  rule picked *after* seeing the data, so it wasn't tested. It could only be
  checked on fresh data.
- **Liquidity targets** (nearest opposite key level, 1–4R) averaged ~1.6–1.9R,
  close to the fixed 2R, and changed nothing.
- **TJR entry with filters:** a few combinations look positive (ES TJR+SMT
  +0.13R, ES TJR full model +0.15R) but on **7–16 trades in 17 months**. That
  is far too few: their 95% ranges run from about −1R to +1R. The full TJR
  stack (sweep → shift → gap → SMT → bias) formed only **7–8 times** per
  index in 17 months.

## Pre-registered design

- **Variants:** SMT · BIAS · SMT + BIAS · FULL_TJR (SMT + BIAS + liquidity
  target), crossed with NQ/ES and RECLAIM/TJR entries, for 16 cells.
- **SMT:** an NQ sweep counts only if ES did not trade beyond its same level
  between the window start and our entry bar (and vice versa).
- **Bias:** prior regular-session close vs its 20-day average; longs only
  above, shorts only below.
- **Liquidity target:** the nearest opposite OR/ON/LDN/PD level at least 1R
  away, capped at 4R; none → 2R.
- **Daily selection:** the first setup of the day (any level, either side)
  that passes the variant's filters.
- **Held from Phase 101:** stop at the sweep extreme, 09:30–11:00 window,
  flat at 12:00, real spread + slippage, out-of-sample from 2026-03-17, and
  the same CANDIDATE bar (Bonferroni over 16, placebo p < 0.05).
- **Checked by hand:** e.g. 2026-10-07, NQ swept its opening-range high while
  ES stayed 6.6 points under its own, so the SMT short was correctly allowed.

## Results (5-minute bars, 2025-05-13 → 2026-10-08)

| Mkt | Entry | Variant | N | Win% | Mean R | Before costs | In-sample | OOS N | OOS mean [95% CI] | Placebo p |
|---|---|---|---|---|---|---|---|---|---|---|
| NQ | RECLAIM | *none (reference)* | 347 | 36% | −0.11 | −0.02 | −0.06 | 139 | −0.18 [−0.39, +0.04] | |
| NQ | RECLAIM | SMT | 234 | 32% | −0.20 | −0.10 | −0.25 | 91 | −0.13 [−0.39, +0.16] | 0.16 |
| NQ | RECLAIM | BIAS | 279 | 31% | −0.25 | −0.15 | −0.20 | 114 | −0.33 [−0.55, −0.10] | 0.74 |
| NQ | RECLAIM | SMT+BIAS | 138 | 30% | −0.27 | −0.16 | −0.28 | 56 | −0.25 [−0.58, +0.11] | 0.48 |
| NQ | RECLAIM | FULL_TJR | 138 | 32% | −0.29 | −0.18 | −0.26 | 56 | −0.34 [−0.64, −0.02] | 0.33 |
| NQ | TJR | *none (reference)* | 53 | 38% | −0.15 | −0.12 | −0.07 | 28 | −0.22 [−0.52, +0.10] | |
| NQ | TJR | SMT | 17 | 41% | −0.08 | −0.04 | −0.14 | 7 | +0.02 [−0.71, +0.76] | — |
| NQ | TJR | BIAS | 28 | 29% | −0.28 | −0.25 | −0.27 | 14 | −0.30 [−0.74, +0.18] | 0.67 |
| NQ | TJR | SMT+BIAS | 8 | 38% | +0.04 | +0.08 | +0.01 | 2 | — | — |
| NQ | TJR | FULL_TJR | 8 | 38% | +0.04 | +0.07 | +0.01 | 2 | — | — |
| ES | RECLAIM | *none (reference)* | 343 | 35% | −0.14 | +0.01 | −0.02 | 140 | −0.32 [−0.53, −0.10] | |
| ES | RECLAIM | SMT | 209 | 31% | −0.27 | −0.10 | −0.30 | 89 | −0.23 [−0.52, +0.07] | 0.36 |
| ES | RECLAIM | BIAS | 283 | 32% | −0.23 | −0.09 | −0.21 | 118 | −0.26 [−0.49, −0.02] | 0.74 |
| ES | RECLAIM | SMT+BIAS | 98 | 32% | −0.25 | −0.10 | −0.42 | 41 | −0.02 [−0.45, +0.44] | 0.47 |
| ES | RECLAIM | FULL_TJR | 98 | 35% | −0.27 | −0.12 | −0.44 | 41 | −0.03 [−0.40, +0.36] | 0.37 |
| ES | TJR | *none (reference)* | 65 | 46% | −0.02 | +0.03 | +0.02 | 22 | −0.08 [−0.49, +0.37] | |
| ES | TJR | SMT | 16 | 50% | +0.13 | +0.18 | +0.17 | 6 | +0.07 [−0.70, +0.98] | — |
| ES | TJR | BIAS | 33 | 52% | +0.09 | +0.13 | +0.30 | 11 | −0.34 [−0.77, +0.11] | 0.86 |
| ES | TJR | SMT+BIAS | 7 | 43% | −0.08 | −0.03 | +0.52 | 4 | −0.52 [−1.03, +0.13] | — |
| ES | TJR | FULL_TJR | 7 | 57% | +0.15 | +0.20 | +0.27 | 4 | +0.07 [−1.03, +1.17] | — |

"—" = too few trades for a placebo (< 10) or a meaningful interval.

## Where this leaves the TJR idea

Across Phases 101–102: 4 levels × 2 entries × 3 exit plans × 4 filter
stacks, on NQ and ES. **Nothing shows a directional edge a computer can
follow.** The only positive pockets are single-digit samples.

That doesn't prove a skilled discretionary trader can't make it work.
Discretion (which days to skip, what a "clean" sweep looks like) isn't
captured here. It does mean that continuing to add filters to this data
would be curve-fitting: with enough combinations, some subset of 7–16 trades
always looks good by chance.

**Ways to check it honestly from here:**
1. **Journal-tag real discretionary trades** ("TJR sweep") and let Analytics
   measure your actual expectancy over 30–50 trades.
2. **Forward-track** the one pocket worth watching (ES, TJR entry + SMT) on
   *new* days only, without changing the rules, until it has 30+ trades.
3. **Longer 1-minute history** (MT5 → Max bars in chart → Unlimited) would let
   the TJR entry be tested at its native timeframe with a bigger sample.
