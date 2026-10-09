# Phase 133 - the user's stop: the internal 1-minute swing, on the MSS entry

Script: `phase133_internal_stop.py` (rows in `.cache/phase101/phase133_rows_*.csv`; `phase132_mss_entry.find_mss` now also returns the internal swing). EXPLORATORY.
MSS entry on 1-minute structure (Phase 132), NQ + ES, Mar 2023 - 25 Sep 2026, no time exit.
- Stop sizes (median): EXT (beyond the extension) 24.8 points, INT (beyond the latest 1-minute swing against the trade) 19.5, WIDE (mirror of the target) 56.
- Gap >= 0.2 (876 trades): INT -0.03R plain, -0.06R half at +1R, -0.08R ladder (interval [-0.16, -0.01], the only one below zero); EXT -0.02 / -0.04 / -0.05R; WIDE -0.02 / -0.02 / -0.02R.
  Per year the INT plain result is positive in 2023-25 (+0.04 to +0.10R) and -0.36R in 2026.
- Gap >= 0.7 (233 trades): INT +0.13R plain (interval [-0.24, +0.55]), +0.05R half, -0.01R ladder; EXT +0.11 / +0.02 / +0.03R; WIDE +0.02 / -0.01 / +0.02R.
- A tighter, structure-based stop changes the win rate (18-32% plain) and the position size, not the average R; costs take a bigger share of a 19-point stop.
Pine: `tradingview/big_gap_fade_strategy.pine` has the stop option "MSS: beyond the internal 1-minute swing (the nearest swing against the trade)".
