# Phase 104: TJR-style discretion as learned selection (walk-forward)

Run 2026-10-09. Code: [`phase104_tjr_selection.py`](../phase104_tjr_selection.py)
(`python -m phase104_tjr_selection`, ~10 min). Follows Phases
[101](PHASE_101_NY_OPEN_SWEEP.md), [102](PHASE_102_TJR_FILTERS.md) and
[103](PHASE_103_TJR_DIAGNOSIS.md).

## Why this phase

Phase 103 found that loose sweep-fades trade daily and lose, while strict
rule sets are rare and break-even. A discretionary trader sees several setups
a day and picks among them. This phase models that directly. It builds every
plausible setup (more levels, flexible trigger timeframe, no hard bias rule),
measures each setup's qualities, and lets a model learn **which ones to take**
from past years only. The model is then graded on years it never saw.

## Verdict (corrected 2026-10-09 — see "Correction" below)

**Not passed. Learned selection does not reliably beat a random pick.**

- **Taking every setup loses clearly:** −0.10R per trade over 4,080 test
  trades (95% CI −0.14 to −0.06).
- **Learned selection:** logistic −0.02R (666 trades, CI −0.11 to +0.08;
  vs random pick −0.07R, placebo p = 0.11). Gradient-boosted −0.05R (630,
  CI −0.15 to +0.05; vs random −0.09R, p = 0.15).
- **By year (boosted):** 2024 −0.09R · 2025 −0.15R · 2026 +0.11R. Logistic:
  +0.01R · −0.11R · +0.05R. Not positive every year.
- **By checklist count** (all NQ/ES candidates, descriptive): 0 items −0.39R ·
  1–3 items −0.08 to −0.15R · 4–5 items −0.08 / −0.04R · 6 items −0.35R (43
  setups). No count is profitable.

### Correction

The first run (preserved as `.cache/phase101/phase104_result_v1_leaky.json`)
reported the boosted model at 0.00R with placebo p = 0.011. Two features
used information from slightly *after* some entries:
- the opening gap used the 09:30 open for 08:30–09:30 setups;
- the 08:30 "news spike" used the full 08:30–08:35 range for setups inside it.

Both now use only data available at the time (the gap to the session-start
price; the spike up to the sweep minute), and the 1-hour bias is cut off at
the session start. With the leak removed, the "selection beats random" result
**no longer holds**.

## What the model found useful (largest logistic weights, last fold)

The model still leans towards the ingredients TJR teaches, but the weights
are small, and the corrected run shows they don't add up to a reliable edge:

| Ingredient | Effect |
|---|---|
| sweep of **equal highs / lows** | + |
| **strong displacement** (size of the reversal from the extreme) | + |
| **wider stop** relative to the day's range (not a tight scalp stop) | + |
| **SMT** (NQ/ES divergence) | + |
| later in the morning (not the first minutes) | + |
| **fair value gap** left by the reversal | + |
| **previous-day** level | + |
| **room** to the next opposite level | + |
| many levels swept at once | − |
| Asia-session level | − |

All weights are small (|coef| < 0.1 on standardised features). None of them
is a strong signal alone.

## Pre-registered design (unchanged from the module docstring)

- **Data:** 1-minute NQ (`NDX100`) and ES (`SPX500`), 2023-04 → 2026-10-08,
  878 trading days, 5,087 candidates (≈ 3 per day per index).
- **Levels:** previous day / week, overnight, Asia, London, opening range,
  and 5- and 15-minute swing highs/lows (including ones formed during the
  morning). Each is liquidity until first breached; equal swings are flagged.
- **Trigger:** a close beyond the 3-bar structure before the sweep on the 1-,
  3- or 5-minute chart within 15 minutes (the earliest wins).
- **Trade:** market entry at that close, stop beyond the extreme (NQ 1.00 /
  ES 0.25), 2R target, flat 12:00, bar spread + slippage.
- **Selection:** walk-forward by year (train on all prior years). Per day and
  index, take the top-scoring candidate if its score is in the top 25% of
  training scores.

## Results by fold

| Model | 2024 | 2025 | 2026 | Pooled | vs random pick |
|---|---|---|---|---|---|
| Gradient-boosted | −0.07R (202) | −0.02R (233) | +0.10R (176) | **0.00R** (611) [−0.10, +0.10] | −0.09R → p = 0.011 |
| Logistic | +0.02R (247) | −0.10R (219) | +0.01R (183) | −0.02R (649) [−0.11, +0.08] | −0.07R → p = 0.10 |

By level family (all candidates, all years): previous day +0.03R (89),
previous week +0.01R (25), and everything else negative (opening range −0.13R,
overnight −0.15R, London −0.22R, 5-minute swings −0.12R, 15-minute swings
−0.07R).

## What it means in practice

- **Selection skill wasn't demonstrated.** After the leak fix, picking by
  TJR's ingredients didn't reliably beat picking at random. A trader with
  better judgment than this model (context, news, tape reading) might still
  do better, and the only way to know is recording your own taken *and
  skipped* setups.
- **As a checklist,** the data favours: equal highs/lows or a previous-day
  level being swept, a strong displacement candle, SMT, a fair value gap, room
  to the next level, and not a tight stop. It disfavours the first minutes of
  the open and Asia-range sweeps.
- **No automated version is profitable** after CFD costs, so none should be
  traded mechanically.
