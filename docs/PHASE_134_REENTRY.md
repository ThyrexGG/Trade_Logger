# Phase 134 - re-entry after a stop-out (a fresh structure shift)

Script: `phase134_reentry.py` (rows in `.cache/phase101/phase134_rows_*.csv`; `phase132_mss_entry.find_mss` got an `after` argument). EXPLORATORY.
MSS 1-minute break entry (Phases 132/133), NQ + ES, Mar 2023 - 25 Sep 2026. After attempt 1 is stopped out before 11:00 the search restarts after the stop
time (a new extension and a new break must print); up to 3 attempts a day.
- Gap >= 0.2, internal-swing stop, plain: attempt 1 -0.03R (876 trades); attempt 2 -0.09R (341, 22% wins); attempt 3 -0.12R (85); all attempts -0.05R (1,302 trades), total -66R vs -25R for attempt 1 only.
  Half at +1R: attempt 1 -0.06R, attempt 2 -0.12R, all -0.08R (interval [-0.14, -0.01]). Extension stop: same direction (attempt 2 -0.10R / -0.12R).
- Gap >= 0.7: attempt 1 +0.13R plain (233), attempt 2 -0.16R (97), all +0.04R. About 40% of gap days have a second attempt, 10% a third.
- Second and third attempts lose more than the first; adding them lowers the total. They give more practice, not more profit.
Pine: `big_gap_fade_strategy.pine` input "MSS entries: max attempts per day" (default 2; 1 = one trade a day).
