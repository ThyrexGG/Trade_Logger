# Phase 94 — Swing-Trading Data Foundation

**Status: COMPLETE.** Data acquisition only — no strategy logic, no
backtesting, no signals, no live execution.

## Purpose

Phases 70–93 established that intraday directional prediction on the
6-instrument 15m FX/gold universe has no edge (four independent
constructions, all null out-of-sample; the ICT/SMC gold strategy failed
independent revalidation in Phase 74). Phase 94 begins a deliberate pivot
to **swing timeframes** (daily bars, days-to-months holds) where the
documented, out-of-sample-surviving edges live: time-series and
cross-sectional momentum, and — for crypto — perpetual funding-rate carry.

This phase only acquires and stores data, with the same
provenance / validation / idempotency discipline as Phase 74's MT5
ingestion.

## What was ingested

### Crypto daily OHLCV — 27 coins, `<BASE>USD`, source Binance spot `api/v3/klines`

Frozen, market-cap-ranked universe (`CRYPTO_UNIVERSE`), selection criteria:
ranked by market cap (CoinGecko top ~60), has both a Binance `<BASE>USDT`
spot pair **and** a Binance USDT-margined perpetual, excludes
stablecoins / wrapped-staked derivatives / tokenised gold, and excludes
names with under ~2 years of history at selection time.

BTC, ETH, BNB, XRP, SOL, TRX, DOGE, ADA, LINK, XLM, BCH, LTC, DOT, AVAX,
UNI, NEAR, ICP, HBAR, SUI, AAVE, ETC, ATOM, FIL, APT, ARB, OP, INJ.

History depth: BTC/ETH from 2017-08; most majors 2018–2020; newest (SUI,
ARB) from 2023. All 27 ingested with **0 rejected candles** and current
data through the run date.

**Historical-only, excluded from the forward universe:** XMR (Monero) —
delisted from Binance spot Feb 2024; its series ends 2024-02-20. History
kept in the store for pre-2024 backtesting completeness only
(`CRYPTO_HISTORICAL_ONLY`).

### Crypto perpetual funding-rate history — 27 coins

Source: Binance USD-M futures `fapi/v1/fundingRate`. Every funding payment
(8-hourly, occasionally 4-hourly) fetched and aggregated to a **daily
summed rate**, stored as a research artifact per coin
(`phase94_funding_daily__<ASSET>`). BTC funding history from 2019-09
(~7,600 payments → ~2,550 days); all 27 coins have ≥3,600 payments.

### Auxiliary FX/metals daily — source Yahoo Finance

- **XAGUSD** (silver, `SI=F`) — ~2,513 daily bars from 2016-09, 0 rejected.
- **EURGBP** (`EURGBP=X`) — ~2,558 usable daily bars from 2016-09; ~45
  thin holiday rows (~1.7%) rejected by the OHLC-consistency gate.

These complete the liquid FX-majors + metals set already in the store
from Phase 74 (EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD,
EURJPY, GBPJPY, AUDJPY, XAUUSD).

## Coverage summary

| Group | Instruments | Momentum-ready (≥400 current daily bars) | Funding-ready |
|---|---:|---:|---:|
| FX + metals | 13 | 13 | n/a |
| Crypto | 27 | 27 | 27 |

**Total swing universe: 40 instruments, all momentum-ready.** This is the
breadth that the 15m FX-only work never had — enough for a cross-sectional
momentum long/short (top third vs bottom third) across each asset class.

## Notes / disclosures

- USDT is treated as USD for crypto research purposes.
- Funding is stored as a **daily summed** rate (the aggregation Phase 96's
  daily-bar backtest needs), not the raw 8-hourly series.
- `momentum_ready` requires both sufficient bar count **and** current data
  (last bar within 45 days) — this is what excludes stale XMR automatically.
- Re-running the ingestion is idempotent (the store's upsert is
  duplicate-safe).
- FX policy-rate / swap data for the FX carry sleeve (Phase 97) is
  **not** acquired here — deferred to the phase that needs it.
- Holdout untouched, live automation disabled, broker transmission
  blocked. No strategy logic of any kind in this phase.

## API

`GET /api/research/swing-data-foundation` — returns the persisted coverage
report (data inventory only; triggers no ingestion). `NOT_COMPUTED` until
`python -m phase94_swing_data_foundation` has run.

## Next phase

**Phase 95 — time-series + cross-sectional momentum** on the combined
40-instrument daily universe: frozen pre-registered rules (3/6/12-month
lookbacks), volatility-scaled sizing, walk-forward through the existing
validation harness with realistic retail costs, honest per-sleeve and
per-asset-class verdicts.
