# Phase 113: TJR's "Liquidity Explained": his London claim and his model, walk-forward optimised

Run 2026-10-09. Code: [`phase113_tjr_liquidity.py`](../phase113_tjr_liquidity.py).
Source: transcript of TJR's "Liquidity Explained" (supplied by the user).
Definitions as he teaches them: Asia 18:00–03:00, London 03:00–08:30 (New York
time); a high = up candle then down candle, a low = the reverse; significant
liquidity = session highs/lows, previous day, 1h/4h highs/lows; confirmation =
a new 5-minute trend after the sweep (low, high, higher low, close above the
high); target = the next untaken level on the other side.

## Part 1: "New York sweeps the London high or low, then makes the day's move"

| | NQ 2023–24 | NQ 2025–26 | ES 2023–24 | ES 2025–26 |
|---|---|---|---|---|
| NY trades through a London high or low by 10:30 | **96%** | **95%** | **95%** | **93%** |
| London LOW taken first (+ reclaimed): London HIGH reached before the sweep low breaks | 22% | 18% | 26% | 23% |
| … random-walk odds for the same distances | 23% | 23% | 20% | 20% |
| … day closes up (vs all days) | 48% (56%) | 45% (52%) | 47% (56%) | 40% (51%) |
| London HIGH taken first (+ reclaimed): London LOW reached first | 27% | 25% | 21% | 20% |
| … random-walk odds | 24% | 22% | 21% | 18% |
| … day closes down (vs all days) | 44% (44%) | 42% (48%) | 40% (44%) | 41% (49%) |

**Reading:** the first half is true. New York takes out a London high or low
on ~95% of days. The second half isn't supported. After the sweep, the
opposite London extreme is reached about as often as chance, and the day
doesn't lean the "reversal" way. After London's *low* is swept first, the day
closes up *less* often than average.

## Part 2: the model, 96 configurations, chosen on 2023–24, judged on 2025–26

Menu: levels {ALL, SESSION, LONDON, HTF} × stop {sweep low, higher low} ×
target {next liquidity, 2R} × management {FIXED, HALF, CUT, RUN, CUT_RUN,
HALF_CUT}. Sweeps 09:30–11:00, entry within 90 min and before 12:00, flat 15:55.

| | NQ | ES |
|---|---|---|
| Best on 2023–24 | SESSION levels · stop below the higher low · next-liquidity target · FIXED: **+0.30R** (111 trades) | HTF levels · stop below the sweep · 2R · FIXED: **+0.11R** (151) |
| **Same config on 2025–26** | **−0.22R** (131 trades; 2025 −0.32, 2026 −0.10) | **−0.09R** (175; 2025 −0.16, 2026 +0.01) |
| Configs positive on 2025–26 | 3% of 96 | 15% of 96 |

**Verdict `NO_EDGE`.** This is the textbook overfitting trap: the setting that
looked best on the past (+0.30R) lost money on the next two years (−0.22R).
The model also matched the user's real 7 Oct trade (both bought 10:10 at
~30,960–30,975).
