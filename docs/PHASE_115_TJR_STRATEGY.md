# Phase 115: TJR's own step-by-step strategy (his 2026 "updated strategy" video)

Run 2026-10-09. Code: [`phase115_tjr_strategy.py`](../phase115_tjr_strategy.py).
Source: transcript of TJR's updated strategy video (supplied by the user), in
which he shows Jan–Jun 2026 results he says came from these rules (≈ 64% win
rate, ≈ 1.33 average reward-to-risk).

## His rules, as coded

1. **Liquidity:** Asia (18:00–03:00) and London (03:00–08:30) session
   highs/lows plus 1-hour and 4-hour highs/lows (2-candle definition), untaken
   at 09:30. New York trades through one; a sweep on either NQ or ES counts
   ("as long as one of the indexes is doing it").
2. **Reversal:** within 60 minutes, a 5-minute break of structure or a
   5-minute inverse FVG.
3. **Retrace:** a 1-minute break of structure against the new direction.
4. **Entry:** a 1-minute break of structure or inverse FVG back in the new
   direction, entering at that close.

Stop beyond the "second high/low" (the retrace extreme); half off at the first
draw on liquidity, stop to breakeven, rest at the next one; flat 15:55. A
48-configuration menu (stop × exits × window × which index sweeps) was
walk-forward tested, chosen on 2023–24 and judged on 2025–26.

## Results

| | NQ | ES | TJR's claim |
|---|---|---|---|
| TJR-faithful version, trades (2023-04 → 2026-10) | 579 | 559 | |
| **Win rate** | **31%** | **33%** | **~64%** |
| Average win / average loss | +1.91R / −1.10R | +1.96R / −1.14R | ~1.33 reward-to-risk |
| **Mean per trade after costs** | **−0.16R** | **−0.11R** | ≈ +0.49R implied |
| Before costs | −0.06R | +0.03R | |
| By year (2023 / 2024 / 2025 / 2026) | −0.16 / −0.03 / −0.25 / −0.20 | −0.20 / +0.13 / −0.24 / −0.14 | |
| **Jan–Jun 2026** (the months he shows) | **−0.11R** (80 trades) | **−0.15R** (84) | strongly positive |

**Walk-forward:** the best NQ configuration on 2023–24 (+0.09R; stop beyond
the sweep, 2R) scored **−0.20R on 2025–26** (95% CI −0.33…−0.08). The best ES
configuration (+0.09R) scored −0.15R. The user's 09:45–10:30 window was the
least bad (NQ −0.06R).

## Verdict: `NO_EDGE` for the rules as stated

Followed mechanically, TJR's step-by-step rules win about a third of the time,
not two thirds, and lose ~0.1–0.16R per trade after CFD costs, including in
the exact months he showed. Whatever produces his results is not in the
written rules. He says himself the strategy's main job is to make him *take
fewer trades*. That selection (and execution, partials, breakeven timing) is
discretionary and not captured here. His account results can't be verified
from here; nothing in this test suggests they're wrong, only that the rules
alone don't reproduce them.

The coded strategy still matches the user's own 7 Oct trade (both long at
10:10 near 30,960–30,975).
