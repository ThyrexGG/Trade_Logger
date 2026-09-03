# Phase 69 — Persistent Historical Data Foundation & Gold Baseline

*First checkpoint of the Phase 69–72 "Historical Strategy Discovery, Gold
Revalidation, Pair Ranking & Trade Setup" master build. Scope was deliberately
limited to the data foundation (§2–§9, §31, §50–§54) so the discovery / ranking /
setup engines (Phase 70–72) build on a real, tested store rather than on
network-fetch-per-request.*

---

## 1. What this phase delivers

| Piece | File | Purpose |
|---|---|---|
| Candle schema | `database.py` `init_db()` (both dialects) | `historical_candles` (PK `asset,timeframe,open_time`), `historical_ingestion_log`, `research_artifacts` |
| Store API | `historical_data_store.py` | validated duplicate-safe upsert, as-of read, coverage, gap detection, data-sufficiency gate, Phase-68 provider adapter, research-artifact persistence |
| Ingestion | `market_data_ingest.py` | yfinance backfill / incremental / duplicate-safe / OHLC-validated / tz-normalised; 4h resampled from 1h; CLI `python -m market_data_ingest` |
| Universe | `research_universe.py` | the 11-instrument research universe (FX majors + JPY crosses + XAUUSD), pip sizes, yf tickers, per-timeframe sufficiency rules, intraday-depth honesty notes |
| Gold baseline | `gold_strategy_baseline.py` | machine-readable recovery of the Phases 14–21 Gold discovery; `PreviousDiscovery` vs `CurrentlyValidatedStrategy`; objective `EdgeStatus` rules |
| API | `api/routers/strategy_research.py` | `GET /api/research/{historical/coverage,universe,gold-baseline}` — read-only |
| Docs | this file, `docs/GOLD_STRATEGY_BASELINE.md` | |
| Tests | `tests/test_phase69_*.py` | 44 tests |

Nothing in the execution / broker / risk / reconciliation / forward-validation
layer was touched. The frozen contract hash and locked holdout are unchanged.

---

## 2. Canonical candle model

`historical_candles`:

```
asset            TEXT      canonical symbol (research_universe.normalise)
timeframe        TEXT      1m | 5m | 15m | 1h | 4h | 1d
open_time        INT/BIGINT epoch SECONDS, UTC, candle-OPEN
open high low close  REAL/DOUBLE PRECISION
volume           REAL      0 when the source has none (FX =X)
source           TEXT      'yahoo' (Phase 69), extensible
source_revision  TEXT      e.g. 'GC=F:1h', 'EURUSD=X:1h:resample4'
data_quality     TEXT      'ok' | 'suspect'
ingested_at      TEXT      ISO-8601 UTC
PRIMARY KEY (asset, timeframe, open_time)   -- duplicate-safe
```

`open_time` is always the candle **open**; the close is `open_time + timeframe`.
Reads with `as_of` keep only candles whose **close ≤ as_of** — identical to the
Phase-68 `historical_market_data._truncate` look-ahead rule.

---

## 3. Validation (`historical_data_store.validate_candle`)

Rejected (counted in `reject_reasons`, never repaired):

- `MALFORMED_FIELDS`, `NON_POSITIVE_OPEN_TIME`, `NON_POSITIVE_PRICE`
- `HIGH_LT_LOW` — `high < low`
- `HIGH_LT_MAX_OPEN_CLOSE` — `high < max(open, close)`
- `LOW_GT_MIN_OPEN_CLOSE` — `low > min(open, close)`
- `DUPLICATE_IN_BATCH`

Flagged `data_quality='suspect'` (stored, usable, visible): `open_time` not
minute-aligned.

`get_coverage` / `detect_gaps` expose structural holes; `data_sufficiency`
returns `AVAILABLE` / `INSUFFICIENT_EVIDENCE` / `NOT_APPLICABLE` with explicit
reasons and a `next_dependency` naming the ingestion command — **never** a
"0 trades / neutral" verdict for missing data (§9).

---

## 4. Data reality — yfinance only, gaps documented honestly

Per the build decision, yfinance is the only wired source. Probed depth:

| TF | yfinance depth | Multi-year discovery / WFO? |
|---|---|---|
| 1d | ~5+ years | ✅ |
| 1h | ~2 years | ✅ (marginal) |
| 4h | resampled from 1h (~2 y) | ✅ |
| 15m | **~60 days** | ❌ `INSUFFICIENT_EVIDENCE` |
| 5m | ~60 days | ❌ |
| 1m | **~7 days** | ❌ — the frozen Gold contract's native TF |

FX is only available as Yahoo `<PAIR>=X` synthetic spot (no real volume, weaker
intraday quality). Gold uses `GC=F` (COMEX front-month future) as an XAUUSD-spot
proxy. `research_universe.timeframe_is_data_capable()` returns `True` only for
`1h/4h/1d`; the discovery engine (Phase 70) must consult it and mark everything
else `INSUFFICIENT_EVIDENCE`.

---

## 5. Populating the store

```
python -m market_data_ingest --universe --timeframes 1d,1h,4h        # full backfill
python -m market_data_ingest --asset XAUUSD --timeframe 1d           # one series
python -m market_data_ingest --incremental --universe               # top-up
```

`*.db` is gitignored, so the store ships **empty** — it is populated per
environment. Until it is, historical evidence stays an honest gap (no fabricated
candles). The Phase-68 provider key defaults to `auto` → the store; set
`HISTORICAL_OHLCV_PROVIDER=none` to force the pre-Phase-69 behaviour.

---

## 6. Gold baseline recovery (§2/§3/§31)

The earlier Gold discovery is **not lost** — it is the frozen Strategy Contract
(`PHASE_20_XAUUSD_FINAL_AUDIT.md` + `PHASE_21_XAUUSD_STRATEGY_CONTRACT.md`).
`gold_strategy_baseline.get_gold_baseline()` returns it as a structured artifact.
See `docs/GOLD_STRATEGY_BASELINE.md`. Phase 69 sets `edge_status =
INSUFFICIENT_EVIDENCE` (revalidation is Phase 71) and every recovered metric
carries `reconstructable=False` because the original 1-minute dataset is not in
the repo.

---

## 7. Tests — `pytest tests/test_phase69_*.py` → 44 passed

- `test_phase69_historical_store.py` (16) — roundtrip, idempotent dupes,
  in-batch dupes, invalid-OHLC rejection (not repaired), ordering, tz
  normalisation, gaps, sufficiency states, as-of / partial-candle exclusion,
  provider provenance, empty-store honest gap, suspect flag, artifact roundtrip.
- `test_phase69_ingestion.py` (8) — frame→candles, 1h→4h resample drops partial
  bucket, universe rejection, monkeypatched-source store, incremental, missing
  yfinance, data-capability flags. All offline.
- `test_phase69_universe.py` (7) — contents, not-USDJPY-only, normalise, pip
  families, yf mapping, sufficiency rules, intraday-honesty notes.
- `test_phase69_gold_baseline.py` (7) — recovered-not-invented, holdout match,
  unverifiable flags, frozen hash, `INSUFFICIENT_EVIDENCE` in P69, objective
  rules, persistence, not-forced-to-win.
- `test_phase69_safety.py` (7) — no execution imports, GET-only, safety barrier,
  health invariants, no secrets, frozen hash + holdout intact.

**Full regression:** `pytest tests/ -p no:randomly` → **1322 passed, 5 skipped,
4 failed**. The 4 failures (`test_stage18_macro`, `test_phase64_macro_scorecard`)
are **pre-existing and environmental** — they reproduce on clean `HEAD` when a
live FRED provider is configured in `.env`; they assert `seed_demo`
unconditionally. Tracked as `TECHNICAL_DEBT.md` P2-9. No Phase-69 module touches
macro.

`npx tsc --noEmit` clean · `npm run build` clean (frontend untouched — UI lands
in Phase 71/72).

---

## 8. Safety

`LIVE_AUTOMATION_ENABLED=False`, `LIVE_BROKER_TRANSMISSION="BLOCKED"` verified via
`/api/health` before/after. No Phase-69 module imports `execution_pipeline`,
`broker_adapter`, `risk_gateway`, `reconciliation`, `order_execution` or
`paper_simulator` (asserted in `test_phase69_safety.py`). All new endpoints are
GET-only with the safety barrier in the body. `.env` stays gitignored; no secret
appears in any response or source file. Frozen hash
`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` and holdout
`N=82 / +0.637R / 58.6% / 2.52` untouched.

---

## 9. Next (Phase 70)

Strategy-discovery framework on top of `backtester.py`: `StrategyDefinition`
registry, `INSTRUMENT × STRATEGY × PARAMS × SESSION × REGIME` evaluation on
**1h/1d store data**, train/test split, `ResearchRankingScore` (decomposable,
never a market score), sample-size treatment, WFO / Monte Carlo / parameter
sensitivity / temporal & pair stability, and the pair × strategy leaderboard.
