# Phase 68 — Historical Market Evidence Engine

*Real, timestamp-correct technical / SMC / seasonality / regime evidence for the
Phase-67 fusion layer, and an honest account of where the data does not exist.*

---

## 1. Evidence-quality audit (done first, before any code)

### 1.1 Where market data lives in the repo

| Component | What it does | Historical / as-of? |
| :-- | :-- | :-- |
| `market_data.get_realtime_candles(sym, tf, count)` | last *N* candles from **MT5 → Binance → Yahoo**, TTL-cached; **synthetic fallback** when every upstream fails (offline) | **NO** — no date range, no `as_of`; returns "now minus N bars" |
| `market_data.get_latest_price / get_latest_tick` | spot price + `change_24h_pct` | **NO** — live only |
| `backtester.run_backtest` | `yfinance.download(sym, period=…, interval=…)` **on demand, over the network** | period-based, network-only, **not persisted** |
| `database.py` | trades / positions / alerts / macro snapshots | **no candle/OHLCV table at all** |
| repo tree | — | **no bundled `.csv` / `.parquet` / OHLCV data files** |

**Conclusion:** the repository has **no historical OHLCV store and no offline
historical price source**. `market_data`'s candle path is live-only; the
backtester's is an on-demand network fetch that is never saved.

### 1.2 Which market calculations are real vs. deterministic priors

| Factor / engine | Current source | Genuinely candle-derived? | Historical-capable with existing infra? |
| :-- | :-- | :-- | :-- |
| `TechnicalStructureFactorEngine` (Phase 55) | **hard-coded `if symbol == …` priors**, fabricated evidence strings | **NO** | needs candles |
| `SmartMoneyStructureFactorEngine` (Phase 55) | **hard-coded symbol priors**, fabricated ("15M Sell-Side Liquidity Swept …") | **NO** | needs candles |
| `SeasonalityFactorEngine` (Phase 55) | **hard-coded month→score priors**, fabricated N ("N = 180 months, 64.2% win-rate") | **NO** | needs multi-year daily history |
| `MarketRegimeFactorEngine` (Phase 55, factor-level) | **hard-coded symbol priors** | **NO** | needs candles |
| `SessionLiquidityFactorEngine` (Phase 55) | derived from `as_of` hour / weekday / holiday calendar | **YES** — pure function of the timestamp | **YES already** |
| `EconomicGrowth/InflationFactorEngine` (Phase 55) | small symbol priors + registry | partial | macro path is as-of-safe (Phase 64/67) |
| `market_data.detect_fvgs(df)` | scans a candle df for 3-candle gaps + mitigation | **YES** | **YES** — takes a df |
| `market_data.detect_order_blocks(df)` | last opposing candle before impulse + invalidation | **YES** | **YES** — takes a df |
| `market_data.calculate_market_structure(df)` | swing highs/lows (centred rolling), HH/HL/LH/LL, BOS/MSS | **YES** | **YES** — takes a df |
| `market_data.calculate_market_regime(df)` | **ADX / +DI / −DI** trend classification | **YES** | **YES** — takes a df |
| `market_data.calculate_volume_profile(df)` | VWAP / POC / VAH / VAL | **YES** (tick volume) | **YES** — takes a df |
| `market_data.calculate_liquidity_zones(df)` | pivot-based liquidity pools | **YES** | **YES** — takes a df |
| `strategies/mtf_engine.calculate_htf_bias(df)` | EMA20/50/200 alignment + structure override | **YES** | **YES** — takes a df |
| `strategies/mtf_engine.align_htf_to_ltf` | look-ahead-safe HTF→LTF merge (tested against a malicious future candle) | **YES** | **YES** — takes dfs |
| `market_data.calculate_mtf_alignment(sym, tf)` | real calc, but **feeds itself from `get_realtime_candles`** | calc yes / feed no | calc **YES**, feed **NO** |
| `CrossAssetRegimeEngine.evaluate_regime` (Phase 57) | 8 benchmarks' **live** `change_24h_pct` | **NO** (live only) | needs historical multi-asset candles |
| `backtester.calc_rsi / calc_atr` | real pandas indicators | **YES** | calc yes / data via network only |

### 1.3 The key insight

Every real SMC / structure / regime function in `market_data.py` **already takes
a candle DataFrame and only looks *inside* that frame** (`df.tail(50)`,
`iloc[-1]`, forward-mitigation loops bounded by the frame). So if we can hand
them a DataFrame **truncated to `candle_time <= as_of`**, they become
timestamp-correct with no change to their logic.

The missing piece is therefore **not new indicators** — it is a
**canonical, as-of-aware candle window interface** that the existing functions
can be fed from.

---

## 2. What Phase 68 builds

```
                 HISTORICAL_OHLCV_PROVIDER   (env, Phase-66-style registry)
                          │
          ┌───────────────┴───────────────┐
   live  (market_data                seeded / vendor
   get_realtime_candles,             (test provider; documented
   only when as_of≈now)              extension point for a real one)
          │                                │
          └───────────────┬────────────────┘
                          ▼
        historical_market_data.get_candle_window(asset, tf, as_of, lookback)
                          │   → truncates every candle to  time <= as_of
                          │   → drops the still-forming final candle
                          ▼
        market_evidence_engine   (real, timestamp-safe calculations)
          technical_evidence   → EMA20/50/200, RSI14, MACD, ATR14
          smc_evidence         → reuses market_data.detect_fvgs / _order_blocks /
                                 calculate_market_structure / _liquidity_zones
          mtf_evidence         → strategies.mtf_engine.calculate_htf_bias per TF
          seasonality_evidence → from available daily history + explicit sample_size
          regime_evidence      → per-benchmark candle windows, per-input ts safety
                          │   → emits canonical api.evidence_model.EvidenceItem
                          ▼
        api/evidence_fusion.py   (Phase 67 — unchanged model / semantics)
          TECHNICAL / SMC / SEASONALITY / REGIME categories now prefer
          market_evidence_engine; deterministic prior is used ONLY in live
          mode and ONLY tagged  provenance = "deterministic_prior",
          source = "model_prior"  — never "historical_ohlcv".
```

### 2.1 Files

| File | Role |
| :-- | :-- |
| `historical_market_data.py` | `CandleWindow` + `get_candle_window(asset, tf, as_of, lookback)` + provider registry. Strict `time <= as_of` truncation. `HISTORICAL_OHLCV_PROVIDER` env. |
| `market_evidence_engine.py` | real timestamp-safe technical / SMC / MTF / seasonality / regime evidence → `EvidenceItem`s. Reuses the existing `market_data` functions. |
| `market_data.py` | **+** `get_candles_with_source()` — non-breaking helper that also reports which upstream served (`mt5` / `binance` / `yahoo` / `synthetic_fallback`) so the synthetic fallback is never mistaken for real data. |
| `api/evidence_model.py` | **+** optional `EvidenceItem` fields: `timeframe`, `latest_input_timestamp`, `calculation_window`. |
| `api/evidence_fusion.py` | `_technical_category` / `_smc_category` / `_seasonality_category` / `_regime_category` rewired; new `provenance="deterministic_prior"` path. |
| `frontend/src/components/intelligence/EvidenceFusionPanel.tsx` | provenance badge — `live candles` / `historical candles` / `model prior (not market-derived)` visibly distinct. |

---

## 3. Historical market evidence contract

Every candle-derived `EvidenceItem` carries:

```
asset  timeframe  metric  value  direction
state  source  source_id  provenance
as_of                       # the snapshot instant
available_timestamp         # == latest_input_timestamp for candle evidence
latest_input_timestamp      # close time of the newest candle used
calculation_window          # e.g. "250×15m candles 2026-08-24T.. → 2026-09-03T.."
```

Rules:
- `latest_input_timestamp <= as_of` — enforced in `get_candle_window` (truncation)
  **and** re-checked by the Phase-67 `_enforce_timestamps` guard.
- The still-forming candle (close time `> as_of`) is dropped.
- Indicator needing *N* observations with `< N` candles available →
  `state = INSUFFICIENT_EVIDENCE` (never backfilled with future candles, never
  the current value for an old `as_of`).
- `provenance` is one of: `live_ohlcv`, `historical_ohlcv`, `deterministic_prior`.
  `deterministic_prior` is **never** labelled `historical_ohlcv` and never
  appears in historical mode.

---

## 4. Timestamp / MTF / SMC-confirmation rules

See `tests/test_phase68_*` — summarised:

- **Technical:** future candle excluded; candle exactly at `as_of` included
  (`<=`); `< warmup` → `INSUFFICIENT_EVIDENCE`; deterministic given the same
  window.
- **MTF:** an HTF candle whose **close** is after `as_of` is not available even
  if its open date matches; `calculate_htf_bias` sees only completed HTF candles.
- **SMC:** a structure whose **confirmation** candle is after `as_of` is
  excluded. Formation vs confirmation vs invalidation are distinct; the evidence
  timestamp is the **confirmation** timestamp (for swing structure that is
  `formation + lookback` candles; for an FVG it is the 3rd candle's close).
- **Seasonality:** only observations with close `<= as_of`; explicit
  `sample_size` + `observation_window`; `< 24` monthly obs (or `< 60` daily for a
  day-of-week cell) → `INSUFFICIENT_EVIDENCE`. With the repo's ~250-candle live
  feed this means seasonality is **almost always `INSUFFICIENT_EVIDENCE`** — an
  honest gap, not a fabricated 15-year sample.
- **Regime:** every benchmark's candle window is truncated independently; a
  missing benchmark series is `MISSING_INPUT`, never silently `0` / neutral.

---

## 5. Deterministic-prior migration matrix

| Prior | Replacement | Historical-capable? | Compatibility risk | Plan |
| :-- | :-- | :-- | :-- | :-- |
| `TechnicalStructureFactorEngine` symbol priors | `market_evidence_engine.technical_evidence` (EMA/RSI/MACD/ATR from candles) | YES when a candle window resolves | Phase-55 `evaluate_asset_edge` still returns the prior — **left intact** for `/api/intelligence/asset-profile` back-compat | fusion prefers real evidence; prior kept but tagged `deterministic_prior`; delete after a real historical provider ships |
| `SmartMoneyStructureFactorEngine` symbol priors | `market_evidence_engine.smc_evidence` (reuses `market_data` SMC fns) | YES when a candle window resolves | same | same |
| `SeasonalityFactorEngine` month priors + fabricated N | `market_evidence_engine.seasonality_evidence` (real sample or `INSUFFICIENT_EVIDENCE`) | only with multi-year daily data (not in repo) | same | prior tagged `deterministic_prior`; real path returns `INSUFFICIENT_EVIDENCE` until a daily-history provider exists |
| `MarketRegimeFactorEngine` symbol priors | folded into `market_evidence_engine` regime/technical | YES (ADX) when candles resolve | same | same |
| `CrossAssetRegimeEngine` live 24h-change | `market_evidence_engine.regime_evidence(as_of)` per-benchmark windows | YES when benchmark windows resolve | Phase-57 `/api/intelligence/summary` still uses the live engine — unchanged | fusion REGIME uses the new path; live summary endpoint unchanged |

**Invariant:** after Phase 68 no code path labels a prior as observed market
evidence. A prior is `provenance="deterministic_prior"`, `source="model_prior"`,
and never appears for a historical `as_of`.

---

## 6. Data availability — the honest bottom line

Because the repo ships **no historical OHLCV**, and tests are offline:

- **Live mode** (`as_of=None`): `TECHNICAL` / `SMC` / `MTF` / `REGIME` become
  **real candle-derived evidence** whenever `market_data.get_realtime_candles`
  reaches a real upstream (MT5 / Binance / Yahoo). If only the synthetic
  fallback is available, the category is `INSUFFICIENT_EVIDENCE`
  (`synthetic_fallback` is never treated as real) — or, if configured, the
  explicitly-tagged `deterministic_prior`.
- **Historical mode** (`as_of=<past>`): real evidence **only when a historical
  OHLCV provider is configured** (`HISTORICAL_OHLCV_PROVIDER`). The repo ships a
  deterministic in-process provider used by the test-suite; a production
  provider (a persisted candle store, or a vendor with a dated-range API) is a
  documented extension point. Without one, these categories stay
  `INSUFFICIENT_EVIDENCE` with `next_dependency` naming the gap.
- **Seasonality**: `INSUFFICIENT_EVIDENCE` in essentially all real
  configurations until a multi-year daily-history provider exists.

This is deliberate: **honest gaps > fabricated readings.**

---

## 7. Remaining technical debt after Phase 68

| Item | Class | State |
| :-- | :-- | :-- |
| **No persisted historical OHLCV store** | data limitation | the single biggest gap. A `candles` table + ingestion job (or a vendor dated-range provider) makes historical `TECHNICAL`/`SMC`/`MTF`/`REGIME` real for arbitrary `as_of`. Register under `historical_market_data.register_provider`. |
| **No multi-year daily history** | data limitation | seasonality stays `INSUFFICIENT_EVIDENCE` in every real config. |
| **Phase-55 `evaluate_asset_edge` still returns priors** | software limitation | left for `/api/intelligence/asset-profile` back-compat; fusion no longer trusts them. Remove once the historical provider lands. |
| **`CrossAssetRegimeEngine` live path unchanged** | software limitation | `/api/intelligence/summary` still live-only; fusion REGIME uses the new as-of path. |
| **Vendor intraday history is short** (yfinance: 1 m ≤ 7 d, 15 m/1 h ≤ 60 d) | licensing / provider limitation | even a yfinance-backed historical provider only reaches ~60 days back for intraday. |

---

## 8. Implemented in this phase

- `historical_market_data.py`, `market_evidence_engine.py` (new)
- `market_data.get_candles_with_source` + `_CANDLE_SOURCE` (source tracking; the
  synthetic offline fallback is now identifiable and never used as evidence)
- `api/evidence_model.py`: `EvidenceItem.{timeframe,latest_input_timestamp,calculation_window}`;
  `EvidenceItem.from_dict` / `CategoryEvidence.from_dict` /
  `AssetIntelligenceSnapshot.from_dict` — round-trip for research storage / audit replay
- `api/evidence_fusion.py`: `TECHNICAL/SMC/SEASONALITY/REGIME` rewired to
  `market_evidence_engine`; `deterministic_prior` provenance path; look-ahead
  guard also checks `latest_input_timestamp`
- `api/ai_context.py`: `ai_snapshot` carries per-category `provenance` + `sources`
  + `latest_input` (lightweight evidence reference); `SYSTEM_INSTRUCTION` marks
  `deterministic_prior` as not-observed
- frontend `EvidenceFusionPanel`: provenance badge (`live candles` /
  `historical candles` / `model prior — not market data`), window + latest-input
  line, `(model prior)` marker on prior items
- tests: `test_phase68_candle_window`, `_market_evidence`, `_fusion_integration`,
  `_reproducibility`, `_invariants`, `_safety`
- `tests/test_stage35b_watchlist.py::test_watchlist_unavailable_price_fallback` —
  added a one-line `_PRICE_CACHE` eviction: the test's `ttl_sec=0.1` was a latent
  ~100 ms race that Phase 68's extra market-data work on the intel path made
  occasionally fail under full-suite timing. Assertion unchanged.
