# Phase 135 - after the MSS, enter on a fair value gap that is retested and respected (or an inverse FVG)

Script: `phase135_mss_fvg_entry.py` (rows in `.cache/phase101/phase135_rows_*.csv`). EXPLORATORY: 12 variants x 2 thresholds. NQ + ES, Mar 2023 - 25 Sep 2026, 1-minute bars, no time exit.
Rules (fixed before the results): MSS as in Phase 132; FVG = a 3-candle gap in the trade direction formed after the extension; IFVG = a gap against the trade formed on the way
to the extension that a candle closed through; entry on a rejection candle (wick reaches the zone, closes back out, in the trade direction) after the break; dead if the extension
is exceeded or yesterday's close touched; stop beyond the zone (ZONE) or beyond the extension (EXT).
- Entry times are spread over the session (median 30 min after the open for FVG, 40 for IFVG; 10th-90th percentile 10-90 min).
- Gap >= 0.2: FVG 615 trades, EXT stop +0.03R plain / +0.01R half at 1R; ZONE stop +0.07R plain / -0.11R half (median stop only 10 points, costs dominate).
  IFVG 234 trades, EXT stop +0.14R plain / +0.09R half (intervals [-0.14, +0.46] / [-0.07, +0.26]); ZONE stop -0.03R / -0.01R.
- Gap >= 0.7 (178 FVG / 78 IFVG trades): +0.1R to +0.4R but with intervals spanning zero by a wide margin (e.g. FVG ZONE plain +0.44R [-0.29, +1.31]).
- Per year the sign flips (FVG ZONE half: 2023 -0.26R, 2024 -0.16R, 2025 +0.01R, 2026 -0.03R). No variant is distinguishable from zero.
Pine: `big_gap_fade_strategy.pine` entry method "MSS + FVG ..." (default) and stop option "FVG: just beyond the gap zone that was respected".
