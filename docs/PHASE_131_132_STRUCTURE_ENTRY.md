# Phases 131-132 - enter on a structure shift instead of at 09:45

Scripts: `phase131_structure_break_entry.py` (v1), `phase132_mss_entry.py` (v2). Rows in `.cache/phase101/phase131_rows_*.csv`, `phase132_rows_*.csv`.
Same big-gap days as Phases 123-130 (NQ + ES, Mar 2023 - 25 Sep 2026, fade toward yesterday's close, no time exit, 10 sessions max). Rules were written
in the script docstrings before the results were seen; all variants are reported. EXPLORATORY.

**v1 (rejected by the user, correctly):** "a close below the latest swing low" triggered on 95% of gap days on 1-minute bars (almost always within minutes
of the open), so it is a rushed entry in disguise. Averages were -0.05 to +0.16R, all inside the noise.

**v2 (a real MSS):** (1) a confirmed swing high that is still the session high since the open (the extension), (2) the pullback low that launched that
final push, (3) a bar CLOSING below it; stop beyond the high; entry at the break, or at a retest of the 50% level of the leg (limit order).
- Entry times are now spread across the session: break median 19 min (1m) / 35 min (5m) after the open, 10th-90th percentile 5-80 min; retest median 28 / 57 min.
  Only 21-78% of gap days produce a valid MSS (5m retest: 21%).
- Results (gap >= 0.2): 1m break -0.02R (plain) / -0.04R (half at 1R); 1m retest -0.08R / -0.10R; 5m break +0.01R / +0.04R; 5m retest +0.12R / -0.02R.
  Gap >= 0.7: 1m break +0.11R / +0.02R; 5m break -0.02R / +0.16R (126 trades); retests +0.08R / -0.16R on 68 trades.
  No variant has an interval that excludes zero. Paired against the 09:45 entry on the same days the difference flips sign across variants.
- Per year: positive in 2025, negative in 2026 for most variants; no variant is stable across the four years.
- Best-looking cells (5m break + half at 1R on big gaps +0.16R; 5m retest plain +0.12R) are 2 of 64 variants examined; chance alone produces such cells.
Conclusion: waiting for a structure shift moves the entry time around and does not create an edge; the same pattern as every management variant.
