# Research Diagnostic Matrix (`research_diagnostics.py`)

*Auxiliary research tooling. Built to answer a follow-up to Phase 74's
`NO_VALIDATED_EDGE` — is the lack of edge broad and structural, or does the
current framework fail only in particular instruments / sessions / regimes /
directions / setups / periods? It is **diagnosis, not optimisation**: every
strategy runs at its registered defaults, no parameter is searched.*

Not tied to a numbered phase (the ORB/VWAP Phase 75 superseded the original
diagnostic-matrix prompt). Kept because it is complete, tested, read-only, and
useful for slicing any strategy's trade stream.

---

## What it does

`build_matrix(timeframe, assets=None, strategies=None)`:

1. Runs **one backtest per (instrument, strategy) at default params** on native
   MT5 data via `strategy_discovery.prepare_data` + `backtester.run_backtest`
   (the exact discovery execution path). `train_split = 0.70` chronological.
2. Tags every trade with its R-multiple and a regime label.
3. Buckets the trades along **pre-declared** dimensions (`SEGMENTATIONS` /
   `SEGMENTATION_RULES_DOC`) — `session`, `day_of_week`, `direction`,
   `liquidity_type`, `year`, `is_oos_split`, `regime` — all from existing project
   definitions, nothing invented post-hoc.
4. Each bucket gets: N, mean/median R, PF, win rate, a deterministic bootstrap CI
   (`research_engine.BootstrapEstimator`, seed 42), a **Bonferroni-widened** CI
   (α = 0.05 / M), the largest single-trade R share, an OOS-only slice, and a
   status (`INSUFFICIENT_SAMPLE` / `EXPLORATORY` / `UNCERTAIN` / `ROBUST` /
   `POSITIVE_CANDIDATE` / `NEGATIVE`).
5. **M** = buckets with N ≥ 30. Reports Bonferroni α, expected false positives at
   α = 0.05, raw positives, and how many survive the widened CI.
6. Chronological (never reshuffled) temporal-stability check on any positive
   bucket.
7. A 7-criterion **promotion gate** (N ≥ 200 · mean R > 0 · nominal CI lower > 0
   · Bonferroni CI lower > 0 · OOS mean R > 0 · no single-trade domination · both
   chronological halves positive). Conclusion: `EXPLORATORY_CANDIDATE` or
   `NO_EDGE_CONFIRMED`.

`scope_note` records any strategy subset run and the excluded strategies'
standing Phase-74 `pair_stability` verdict, so a reduced run stays auditable.

---

## Safety

- No execution / broker / risk / reconciliation / forward module imported
  (asserted by `test_no_execution_or_broker_imports`).
- The frozen holdout is never read — no `LOCKED_HISTORICAL_BASELINE` /
  `forward_accumulation` / `forward_validator` reference
  (`test_module_never_reads_the_frozen_holdout`). The matrix records the frozen
  contract hash it saw and `holdout_untouched: true`.
- `LIVE_AUTOMATION_ENABLED` / `LIVE_BROKER_TRANSMISSION` untouched.

---

## Run / read

```
HISTORICAL_OHLCV_PROVIDER=mt5 python -m research_diagnostics 15m
HISTORICAL_OHLCV_PROVIDER=mt5 python -m research_diagnostics 15m "ict_2022_sweep_mss_fvg,smc_continuation_bos_fvg,trend_continuation_ema"
```

Persists the `research_diagnostic_matrix` artifact.
`GET /api/research/diagnostic-matrix` serves it read-only (`NOT_COMPUTED` until
the CLI runs). Deterministic — same store state ⇒ byte-identical rows
(`test_matrix_is_reproducible`).

Tests: `tests/test_research_diagnostics.py` (16).

**Note:** as of this writing no full matrix run has been persisted — every
attempt was cut short (memory pressure, then a scope reduction, then the phase
was redefined). The module and tests are complete; a run just needs to finish.
