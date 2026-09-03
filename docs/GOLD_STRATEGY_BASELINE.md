# Gold (XAUUSD) Strategy Baseline — Recovered Previous Discovery

*Permanent research reference (Phase 69, §2/§3/§31). Machine-readable form:
`gold_strategy_baseline.get_gold_baseline()`; persisted snapshot:
`research_artifacts` key `gold_strategy_baseline`.*

---

## The previous discovery was never lost

The project's earlier strategy-discovery work (**Phases 14–21**) converged on
XAUUSD, and that result **is the frozen Strategy Contract** the whole
forward-validation half of the repo is built around:

- Specification: `PHASE_21_XAUUSD_STRATEGY_CONTRACT.md`
- Adversarial audit: `PHASE_20_XAUUSD_FINAL_AUDIT.md`
- Contract hash: `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`
  (the master-prompt string `…21bda769…` is a known transposition typo; the repo
  value `…21dba769…` is authoritative and must not change)
- ~45 `xauusd_forward_*.py` modules = the live forward-validation apparatus

---

## Strategy (Phase-21 frozen contract, Model D)

| Field | Value |
|---|---|
| Name | XAUUSD True Multi-Timeframe ICT/SMC |
| Instrument | XAUUSD (Gold), `GC=F` proxy for historical data |
| Timeframe stack | 1D bias → 4H draw-on-liquidity → 15M setup → 5M confirmation → **1M FVG limit entry** |
| Execution TF | 1m |
| Session policy | London 07:00–11:00 UTC and London/NY overlap 12:00–16:00 UTC only |
| Entry | 15M liquidity sweep + MSS (body close beyond fractal swing) + displacement FVG (body ≥ 65 % range, ≥ 0.5·ATR₁₅ₘ); 5M aligned FVG confirmation; limit at the boundary (candle-3 high/low) of the first aligned 1M FVG |
| Stop | 1M setup swing ± 0.5·ATR(1M); bounded 5.0–35.0 pips; reject if > 35 pips |
| Target | Fixed 3.0R (or 4H DOL if higher structural congruency, cap 7.0R); TP1 50 % at 2.0R then BE +0.1R |
| Risk | ≤ 1.0 % per trade (default 0.5 %); max 1 XAUUSD position; portfolio aggregate ≤ 5 % |
| Filters | 1D bias must be decisive; spread ≤ 4.0 pips; DOL must offer ≥ 2.0R |

---

## Recovered metrics — **all `reconstructable = false`**

The Phase 19/20 numbers were produced from a **1-minute XAUUSD dataset that is
not in the repository** (`TECHNICAL_DEBT.md` P1-6). They are recorded here from
the research documents, not reproduced:

| Metric | Value | Source | Note |
|---|---|---|---|
| Holdout N | 82 | PHASE_20 §3 | locked, never re-optimised |
| Holdout E[R] | **+0.637 R** | PHASE_20 §3 | 95 % bootstrap CI [+0.477R, +0.817R] |
| Holdout win rate | 58.6 % | PHASE_20 §3 | |
| Holdout profit factor | 2.52 | PHASE_20 §3 | |
| Holdout max drawdown | 4.0 R | PHASE_20 §9 | |
| Avg SL distance | 14.5 pips | PHASE_20 §3 | Model D |
| Monte Carlo median return | +102.8 R | PHASE_20 §9 | 10k runs — **artifact not in repo** |
| P(20R drawdown) | 0.0 % | PHASE_20 §9 | **artifact not in repo** |
| 3× friction-stress E[R] | +0.317 R | PHASE_20 §8 | 6.0 pip spread / 3.0 pip slippage / 250 ms |

**Explicitly unverifiable from the repo:** all backtest numbers above; the WFO
"100 % window stability" claim; the 10,000-run Monte Carlo distribution; the
6-execution-model and SL/TP sensitivity tables; the cross-asset transfer table.

The locked holdout constants (`N=82 / +0.637R / 58.6% / 2.52`) live canonically in
`xauusd_forward_accumulation.HistoricalVsForwardComparator.LOCKED_HISTORICAL_BASELINE`
and are imported (not re-typed) by `gold_strategy_baseline.py`.

---

## Previous Discovery vs Currently Validated Strategy

- **Previous Discovery** — the record above. Historical fact. Read-only.
- **Currently Validated Strategy** — what the Phase 70 discovery/robustness
  pipeline can independently confirm *today* on real store data. Filled in by
  **Phase 71** (`revalidated_metrics`, `latest_oos_metrics`, `wfo_status`,
  `monte_carlo_status`, `last_validated_at`).

Phase 69 leaves the "currently validated" side empty and `edge_status =
INSUFFICIENT_EVIDENCE`.

---

## Edge status — objective rules

| State | Rule |
|---|---|
| `VALIDATED` | Phase-71 revalidation PASS on the same contract (OOS E[R] > 0 with lower confidence bound > 0; WFO majority of windows positive; Monte Carlo P(ruin) < 5 %) AND no forward sample with N ≥ 20 contradicts it |
| `HEALTHY` | `VALIDATED` AND a forward sample N ≥ 20 has E[R] within 1 bootstrap SE of the revalidated OOS E[R] |
| `DEGRADED` | A forward sample N ≥ 20 has E[R] below (revalidated OOS E[R] − 2 bootstrap SE) but still ≥ 0. Single trades never trigger this |
| `INVALIDATED` | Revalidation FAILED, OR a forward sample N ≥ 30 has E[R] < 0 with an upper confidence bound < 0 |
| `INSUFFICIENT_EVIDENCE` | Default. Revalidation not run, or the data / forward sample is not present. **Current state (Phase 69).** |

---

## Native-timeframe caveat

The contract executes on **1-minute** structure. yfinance provides only ~7 days
of 1m data, so a like-for-like N=82 multi-year revalidation on the native
timeframe is **not possible** with the Phase-69 data source. Phase 71 will run the
contract's logic on **1h** structure as the closest defensible approximation and
report the timeframe substitution explicitly — it will not claim equivalence to
the frozen holdout. A true native revalidation needs an intraday OHLCV provider.

Gold is a **protected baseline**, not a guaranteed winner: the Phase 70 ranking
may place another instrument above it on current evidence, and that is a valid
outcome.
