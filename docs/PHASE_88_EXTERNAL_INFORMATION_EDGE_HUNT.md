# Phase 88 — External Information Acquisition & Aggressive Directional Edge Hunt

**Status: COMPLETE.** No live-execution artifact of any kind exists in
this phase's code or this document.

**Final verdict: `NO_EXTERNAL_INFORMATION_FOUND`.** One genuinely new,
independent dataset was acquired (Yahoo Finance daily DXY, VIX, US 10-Year
yield, COMEX gold futures, WTI crude futures) and tested via six
pre-registered, hypothesis-driven candidates. All six showed essentially
zero incremental directional information (every delta within ±0.0004 of
the frozen baseline, none both positive and CI-excluding). Tier 1/2
(economic surprise) and Tier 4 (order flow) remain confirmed unavailable
by direct inspection, not assumption.

## 1. Purpose

Phase 87 established that cross-market information built from
already-owned MT5 instruments (same feed) adds essentially zero
incremental direction information. This phase's explicit mandate was
different: **acquire** genuinely new, independent information — not
re-slice the existing dataset — and determine whether it creates an
actionable directional edge.

## 2. Repository State (verified, not assumed)

`HEAD == origin/main == 3577266` (Phase 87), working tree clean, 1865
passed / 6 skipped / 0 failed, frozen Gold contract hash unchanged —
confirmed at the start of this phase.

## 3. Data Source Tier Audit

### Tier 1/2 — Economic surprise / macro-with-timestamps: `CONSENSUS_DATA_UNAVAILABLE`

`xauusd_daily_preflight.ForexFactoryProvider.get_calendar()` was inspected
by source: it contains no `requests`/`urllib`/`httpx`/`http.client` call
anywhere in the file, and its records' `actual` field is hard-coded
`None` — **it is a stub, not a live fetch**, returning illustrative
forecast/previous values only. `api/providers/fred_provider.py` (Phase
65) supplies real historical actuals only, with no consensus/forecast
field (re-confirmed here, consistent with Phase 87's own finding).
`macro_intelligence_engine.py`'s forecast-bearing records are a 27-entry
illustrative seed dataset, not a multi-year archive. Per the master
prompt's explicit rule (§5), **no substitute was fabricated** — no
actual-minus-previous stand-in, no reconstruction of historical forecasts
from today's values.

### Tier 3 — Independent cross-market data: **AVAILABLE, acquired**

`yfinance` is already a repository dependency (Phase 69–73 ingestion) —
zero new credentials, zero cost, no new account. It supplies real,
**independent** (different vendor: Yahoo Finance, sourcing ICE/CBOE/CME
data — explicitly not the MT5 broker feed used everywhere else) daily
historical data for:

| Symbol | Series | Coverage (verified) |
|---|---|---|
| `DX-Y.NYB` | US Dollar Index (DXY) | 2016-01 → 2026-09, 2684 daily bars |
| `^VIX` | CBOE Volatility Index | 2016-01 → 2026-09, 2684 daily bars |
| `^TNX` | US 10-Year Treasury yield | 2016-01 → 2026-09, 2682 daily bars |
| `GC=F` | COMEX gold futures | 2016-01 → 2026-09, 2682 daily bars |
| `CL=F` | WTI crude futures | 2016-01 → 2026-09, 2683 daily bars |

This is the **one** new dataset acquired in this phase. It was fetched
once and snapshotted into the existing generic artifact store
(`historical_data_store.save_artifact`) — every subsequent run reuses the
persisted snapshot rather than re-fetching, so results stay deterministic
even though the live data could later change or be revised by Yahoo.

### Tier 4 — Order flow / microstructure: `DATA_SOURCE_UNAVAILABLE`

Reused verbatim from Phase 84/85: `copy_ticks_range` is never called
anywhere in this repository; the persisted schema has no
bid/ask/spread/depth column.

## 4. Causal Timestamp Contract

A daily external bar dated `D` is treated as known **no earlier than
`D+1` day, 00:00 UTC** — a deliberately conservative buffer. Real US-market
daily closes are typically ~20:00–22:00 UTC, but exact settlement-vs-
session timing varies by symbol, exchange, and DST, and this repository
has no authoritative per-symbol close-timestamp table. This buffer can
only make a feature *less* available (excluding a few same-day 15m bars
near the boundary), never more — a conservative, disclosed choice, not an
attempt to maximize usable sample. Implemented as a `merge_asof`
backward join: each 15m target row receives the most recent external
observation whose availability timestamp is at or before its own
`prediction_timestamp`; rows with no qualifying prior observation are
dropped, never filled with a future or default value.

## 5. Data-Source Independence Disclosure (per candidate)

| Field | Value |
|---|---|
| Source / Provider | Yahoo Finance (`yfinance`) |
| Instrument | DX-Y.NYB, ^VIX, ^TNX, GC=F, CL=F |
| Timezone | UTC (converted at ingestion) |
| Timestamp semantics | One row per UTC calendar date, daily close; +1 day availability lag applied |
| Historical coverage | 2016-01 → 2026-09 (spans the full Phase 83 discovery/confirmation window) |
| Data type | Daily OHLC close (close only used) |
| Same-feed or independent | **Independent** — different vendor and underlying market than the MT5 broker feed |

## 6. Pre-Registered Candidate Registry (six, frozen, never expanded)

Each candidate has its own economic hypothesis and its own hypothesis-
motivated target instrument(s) — no combinatorial "test everything against
everything":

| ID | External series | Target(s) | Hypothesis |
|---|---|---|---|
| E1 | DXY | USDJPY, EURUSD, GBPUSD, XAUUSD | USD repricing |
| E2 | UST10Y | USDJPY, EURUSD, GBPUSD, XAUUSD | Rate-differential repricing |
| E3 | VIX | AUDJPY | Risk-off carry unwind |
| E4 | VIX | XAUUSD | Safe-haven demand |
| E5 | GC=F (gold futures) | XAUUSD | Cross-venue lead-lag (COMEX → MT5 spot) |
| E6 | CL=F (crude futures) | USDCAD | Petrocurrency |

E1/E2's target list is restricted to the four instruments with a direct,
standard USD-repricing hypothesis (USDJPY = USD base; EURUSD/GBPUSD = USD
quote; XAUUSD = USD-denominated) — GBPJPY and AUDJPY are JPY/AUD crosses
with no clean direct-DXY story and are excluded rather than assigned an
arbitrary sign, per the master prompt's explicit "no dataset without a
clear hypothesis" rule (§7). AUDJPY instead has its own clean hypothesis
under E3. USDCAD (E6's target) is outside the canonical 6-instrument
universe used everywhere else in this research program — a disclosed,
deliberate exception, since it is the only economically sensible target
for the petrocurrency hypothesis and 15m MT5 data for it is already
stored (one of the 11 already-owned instruments, per Phase 84's own
inventory).

## 7. Candidate Results

| ID | N (disc/conf) | Baseline R² | Δ R² (rank feature) | 95% CI | Excludes 0 | Placebo Δ |
|---|---|---|---|---|---|---|
| E1 (DXY) | 233,978 / 116,024 | 0.00174 | −0.0001 | [−0.0004, 0.0002] | No | −0.0001 |
| E2 (UST10Y) | 233,978 / 116,024 | 0.00174 | −0.0002 | [−0.0004, −0.0000] | Yes (negative) | −0.0000 |
| E3 (VIX→AUDJPY) | 58,487 / 29,346 | 0.01859 | −0.0004 | [−0.0007, 0.0001] | No | −0.0000 |
| E4 (VIX→XAUUSD) | 59,942 / 27,986 | −0.00272 | −0.0001 | [−0.0002, 0.0000] | No | −0.0002 |
| E5 (GC=F→XAUUSD) | 59,942 / 27,986 | −0.00272 | 0.0000 | [−0.0000, 0.0000] | No | 0.0000 |
| E6 (CL=F→USDCAD) | 57,986 / 29,346 | 0.00321 | −0.0004 | [−0.0008, 0.0000] | No | 0.0000 |

E2's confidence interval technically excludes zero, but its point estimate
is **negative** (−0.0002) — the candidate classifier correctly requires a
*positive* CI-excluding delta before considering materiality, so this is
still `NO_EXTERNAL_INFORMATION_FOUND`, not a promoted (negative-direction)
finding. Every placebo is consistent with a genuine null (small, mixed-sign,
never larger than the already-tiny real effect).

## 8. Verdicts Per Candidate

All six: **`NO_EXTERNAL_INFORMATION_FOUND`.**

## 9. Determinism & Holdout

Two independent in-process evaluations of the full candidate set produced
byte-identical results (`determinism.match: True`). Frozen Gold contract
hash before and after this phase:
`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` —
**unchanged**. `LIVE_AUTOMATION_ENABLED=False` and
`LIVE_BROKER_TRANSMISSION=BLOCKED` unchanged throughout.

## 10. Researcher-Degree-of-Freedom Ledger

Recorded in full in the persisted artifact: 2 Tier-1/2/4 feasibility
audits, 1 Tier-3 data acquisition (5 symbols, fetched once), 6
pre-registered candidates each evaluated with exactly 3 models (baseline,
+raw external feature, +rank feature) plus 1 placebo — 18 model fits and
6 placebo fits total, run once each on the frozen discovery/confirmation
split. No threshold, lag, or target list was searched, tuned, or expanded
after seeing any result — the +1-day availability lag, the target
restriction for E1/E2, and all six hypotheses were fixed before the
snapshot was even fetched.

## 11. Limitations

1. This phase tested six specific, hypothesis-driven constructions of the
   acquired Tier-3 data (simple daily return and a trailing-rank
   transform) — not every conceivable transform or lag of DXY/VIX/yields/
   futures. This is a deliberate scope choice (master prompt §7's
   "no data graveyard" rule), not an exhaustive search.
2. The +1-day availability lag is a conservative approximation, not a
   verified per-symbol settlement timestamp — a genuinely tighter
   (same-day, intraday-aware) causal alignment was not attempted, since
   Yahoo Finance's free daily data does not carry sub-day timestamps to
   align against.
3. This phase establishes an absence of *linear, Ridge-detectable*
   incremental information from these five specific external series; it
   cannot rule out a nonlinear relationship the deliberately restricted
   model family would not detect, nor a relationship at a resolution
   finer than daily.

## 12. Recommendation

This is now the **fourth** independent directional construction (Phase 83
interactions, Phase 86 momentum+volume, Phase 87 same-feed cross-market,
Phase 88 independent Tier-3 external data) to find no directional edge.
Combined with Phase 88's own confirmation that Tier 1/2 (economic
surprise) and Tier 4 (order flow) are genuinely unavailable without new
paid data acquisition, the honest conclusion is: **TradeLogger has now
exhausted every currently-accessible information source for a directional
edge on the canonical universe at 15m.** Any further directional-edge
research requires either (a) a paid, higher-tier data subscription
(a genuine economic-surprise/consensus feed, or genuine historical
order-flow data) — a decision requiring explicit sign-off given cost and
new-vendor risk, not something to acquire unilaterally — or (b) an
explicit pivot away from direction entirely, toward Phase 85's confirmed
magnitude information used for a non-directional purpose (e.g.,
volatility-aware risk framing), which remains a separate, unscoped
research question.
