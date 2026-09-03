# Phase 70 — Strategy Discovery & Pair × Strategy Ranking

*Second checkpoint of the Phase 69–72 master build. Builds the discovery engine
on top of the Phase-69 persistent candle store and the existing
`backtester` / `research_engine`, and produces a reproducible pair × strategy
leaderboard.*

---

## 1. What this phase delivers

| Piece | File | Purpose |
|---|---|---|
| Discovery engine | `strategy_discovery.py` | `StrategyDefinition` registry (machine-readable), store→backtester adapter, `discover()` (one INSTRUMENT×STRATEGY×PARAMS run), `ResearchRankingScore` (decomposable), session/regime/temporal breakdowns |
| Ranking + robustness | `pair_ranking.py` | orchestrates the universe × strategies, walk-forward, Monte Carlo, parameter sensitivity, pair-stability classification, leaderboard, artifact persistence + CLI |
| API | `api/routers/strategy_research.py` | `GET /api/research/{strategies,strategies/{id},pair-ranking}` — reads the persisted artifact only, never computes |
| Frontend | `pages/StrategyDiscoveryPage.tsx` (+ hook/api/types) | `/research/discovery` — verdict, leaderboard, Gold detail, strategy definitions, data-foundation coverage |
| Tests | `tests/test_phase70_*.py` | 25 tests (discovery / pair-ranking / safety) |
| Docs | this file | |

No execution / broker / risk / reconciliation / forward-validation file was
touched. Frozen contract hash and locked holdout unchanged.

---

## 2. Discovery timeframe stack

Real multi-year depth exists only for **1h / 4h / 1d** (Phase 69, yfinance
limit). The stack mirrors the backtester's own map:

| base | struct | bias |
|---|---|---|
| 1h | 4h | 1d |
| 4h | 1d | 1d |
| 1d | 1d | 1d |

`15m / 5m / 1m` → `INSUFFICIENT_EVIDENCE` with `next_dependency = "an intraday
OHLCV provider"`. Never a fabricated 0-trade result.

---

## 3. Strategy family set (§11)

Wraps the existing `strategies/` registry — no SMC/MTF logic reimplemented:

| id | registry strategy | family |
|---|---|---|
| `ict_2022_sweep_mss_fvg` | ICT 2022 Model | liquidity sweep + MSS + FVG |
| `liquidity_sweep_reversal` | Liquidity Sweep Reversal | sweep + rejection |
| `smc_continuation_bos_fvg` | USDJPY SMC Continuation | HTF bias + BOS + FVG |
| `trend_continuation_ema` | Trend Continuation | EMA pullback |
| `mean_reversion_rsi` | Mean Reversion | RSI reversion |

Each has an explicit `StrategyDefinition` (entry/exit/stop/target text +
`parameter_schema` with `sl_atr` / `tp_atr` grids).

---

## 4. Anti-lookahead (§14–§17)

Discovery reuses the backtester's guarantees and adds a store-level one:

- **Next-bar execution** — `backtester.run_backtest` executes on the bar *after*
  a signal; limit fills require a touch.
- **As-of candle windows** — `store.get_candles(as_of=…)` truncates to
  `open_time + timeframe ≤ as_of` (same rule as Phase 68).
- **MTF alignment** — `mtf_engine.align_htf_to_ltf` merges only the *last
  completed* HTF candle (already look-ahead-tested).
- **SMC features** — `smc_utils.add_smc_features` is `.shift()`-based, no future.
- Dedicated test: a backtest over candles `[0:k]` produces exactly the trades of
  the full-series backtest whose entry falls before `k`
  (`test_no_lookahead_future_candles_do_not_change_past_trades`).

---

## 5. Metrics (§20) & ranking (§21–§23)

Per candidate: N, win rate, avg/median R, expectancy, profit factor, gross
return R, max drawdown R, largest win/loss, max consecutive losses — computed for
**IS and OOS separately** (`train_split = 0.70`). OOS 95% CI via
`research_engine.BootstrapEstimator` (deterministic seed 42). Scorecard via
`research_engine.ScorecardClassifier` (STRONG / PROMISING / UNCERTAIN / WEAK /
FAILED / INSUFFICIENT DATA).

**`ResearchRankingScore`** — the leaderboard sort key. Weighted blend of 6
*visible* components (OOS expectancy, OOS CI-lower, profit factor, sample size,
drawdown, WFO stability); `raw_metrics` always attached; a candidate with
`< 30` OOS trades is **not scored** (`state = INSUFFICIENT_EVIDENCE`). It is
explicitly *not* a `MarketScore` / `TradeScore` and never drives an order
(`test_no_market_or_trade_score_naming`, `test_ranking_is_not_by_raw_profit`).

---

## 6. Robustness (§25–§29) — `--deep`

- **Walk-forward** (`walk_forward`) — store-based: `windows` chronological slices;
  grid-search sl/tp on the IS head, apply best to the OOS tail, stitch OOS trades;
  `stability = fraction of windows with positive OOS E[R]` → ROBUST / FRAGILE /
  UNSTABLE.
- **Monte Carlo** (`monte_carlo`) — `backtester.run_monte_carlo` on the stitched
  OOS distribution (drawdown / ruin / streak).
- **Parameter sensitivity** (`parameter_sensitivity`) — perturb `sl_atr` / `tp_atr`
  by ±10 % / ±20 %; `overfit_risk = HIGH` if the profitable neighbourhood
  collapses.
- **Temporal stability** — per calendar year breakdown (§28), from real trade
  entry years only.
- **Pair stability** (`classify_pair_stability`) — GOLD_SPECIFIC / JPY_FAMILY /
  FX_WIDE / MULTI_ASSET / NARROW / NO_EDGE_ANYWHERE. A Gold-only edge is a valid
  classification, not a rejection (§29).

---

## 7. Performance (§60)

Discovery compute is **never** on an API request. It is an offline CLI:

```
python -m pair_ranking --timeframe 1h                 # quick — discovery only
python -m pair_ranking --timeframe 1h --deep          # + WFO / MC / sensitivity
python -m pair_ranking --timeframe 1h --assets XAUUSD,EURUSD
```

Persists to `research_artifacts` key `pair_ranking`. The API reads that snapshot
(warm ≈ a single DB row read). One `discover()` run ≈ 5–35 s on ~17 k 1h bars
(`ict_2022` is the slow one); an in-process `prepare_data` cache means each
`(asset, timeframe)` candle pull + DataFrame build happens once per ranking run,
not once per strategy. Full universe quick run ≈ 8–12 min.

---

## 8. First real result (1h, quick, XAUUSD/EURUSD/USDJPY)

```
 #  ASSET    STRATEGY                    OOS E[R]     PF    WR%     N    RRS  CARD
 1  XAUUSD   smc_continuation_bos_fvg      +0.331   1.53   38.5    52   33.2  UNCERTAIN
 2  XAUUSD   ict_2022_sweep_mss_fvg        +0.106   1.32   67.4    46   24.8  UNCERTAIN
 3  XAUUSD   trend_continuation_ema        +0.078   1.13   41.4    87   20.0  UNCERTAIN
 …  (all others FAILED)

VERDICT: NO ROBUST EDGE FOUND — candidates exist but none clears positive OOS
lower-CI + N>=50 + WFO stability >= 0.5 on the current data
```

This is the honest §69 outcome. XAUUSD leads the *unvalidated* candidates —
consistent with the historical Gold finding — but every candidate is `UNCERTAIN`
or `FAILED` on 1h data. The frozen Gold contract executes on **1-minute**
structure with tight structural stops, which yfinance cannot supply; 1h with
fixed ATR stops is a different, weaker strategy. Phase 71 reports this
timeframe substitution explicitly rather than claim equivalence.

### 8b. Deep run (`--deep --deep-top 8`, artifact `96608cc81da6`)

WFO / Monte Carlo / parameter-sensitivity on the 8 top candidates:

| Asset | Strategy | WFO stability | Overfit risk | MC ruin |
|---|---|---|---|---|
| **XAUUSD** | **ict_2022_sweep_mss_fvg** | **1.0 (ROBUST)** | **LOW** (nbhd 1.0) | 0% |
| XAUUSD | smc_continuation_bos_fvg | 0.67 (FRAGILE) | LOW (nbhd 0.9) | 0% |
| USDJPY | ict_2022_sweep_mss_fvg | 1.0 (ROBUST) | HIGH (nbhd 0.0) | 0% |
| USDCAD | smc_continuation_bos_fvg | 0.67 (FRAGILE) | HIGH | 0% |
| others | trend / ict | 0.33 (UNSTABLE) | HIGH | 0% |

Verdict unchanged: **NO ROBUST EDGE FOUND**. But the deep pass isolates **XAUUSD
`ict_2022_sweep_mss_fvg`** as the single most robust candidate — WFO-stable across
all windows *and* parameter-insensitive (profitable across the full ±20%
neighbourhood) *and* zero Monte-Carlo ruin. It is held back from `VALIDATED`
only by sample size (OOS N=46 < 50) and a bootstrap CI that still crosses zero
([−0.137R, +0.351R]). This is consistent with the historical Gold discovery and
points at exactly what would confirm it: more trades, i.e. a lower timeframe with
real intraday depth. `pair_stability` for every strategy is `NO_EDGE_ANYWHERE`
(no candidate has a positive OOS lower confidence bound).

---

## 9. Safety

`LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = "BLOCKED"` verified
before/after. No Phase-70 module imports `execution_pipeline`, `broker_adapter`,
`risk_gateway`, `reconciliation`, `order_execution`, `paper_simulator`,
`capital_sync` or `mt5_sync` (`test_phase70_safety.py`). All endpoints GET-only.
Frozen hash `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`
and holdout `N=82 / +0.637R / 58.6% / 2.52` untouched. The Gold baseline stays
`edge_status = INSUFFICIENT_EVIDENCE`.

---

## 10. Next (Phase 71)

Gold revalidation baseline — run the frozen contract through this pipeline on
1h/1d, fill `GoldStrategyBaseline.revalidated_metrics`, and produce the
old-vs-new comparison with the timeframe-substitution caveat stated up front.
