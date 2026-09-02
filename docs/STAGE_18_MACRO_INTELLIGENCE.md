# STAGE 18 — Market & Macro Intelligence Foundation

**Baseline:** `83c7272` (Stage 15). **Type:** read-only foundation, built as a
preview to be refined against user-supplied reference screenshots (see §18I).

TradeLogger's own implementation — NOT a clone of any external product. Built on
the existing deterministic macro engine, a new provider abstraction, a clean
read-only API, a native dashboard and an allowlisted Gemini context.

---

## Architecture

```
provider (api/macro_provider.py)          <- swappable; default = seeded demo data
   -> normalizer  -> EconomicEvent
   -> surprise engine (api/surprise_engine.py, per-indicator config, deterministic)
   -> macro_intelligence_engine.*  (REUSED verbatim: strength / factor groups /
      FX relative strength / gold macro model)
   -> service (api/macro_service.py)  <- filters, shapes, TAGS PROVENANCE
   -> API (api/routers/macro.py)  GET-only
   -> React (/research/macro)
   -> allowlisted AI context (api/ai_context.py :: _macro_context)
   -> read-only Gemini assistant
```

Each layer is independently testable.

---

## Reuse audit (done first)

`macro_intelligence_engine.py` (1609 lines, Phase 56) **already implements** the
surprise engine, per-country economic strength, 5 factor groups
(GROWTH / INFLATION / LABOR / MONETARY_POLICY / SENTIMENT_POSITIONING), FX
relative strength, a dedicated gold macro model, factor-conflict detection,
freshness auditing and a snapshot store — with 13 `test_phase56_*` +
`test_phase55_macro` + `test_phase57_surprise_heatmap` covering it. **Stage 18
reuses all of it unchanged** and adds only: a provider abstraction, a
standalone per-indicator surprise config, the service/API/UI/Gemini layers.

**Data-integrity finding:** `EconomicDataRegistry.seed_canonical_registry()`
seeds *synthetic* 2026 economic values (realistic shape, not real market data),
and only USD / EUR / GBP / JPY have data. The entire Stage 18 surface therefore
tags **`provenance: "seed_demo"` / `provider_is_live: false`** on every response,
the UI shows a prominent "DEMO / SEEDED DATA" banner, and CHF / CAD / AUD / NZD
return **`INSUFFICIENT_EVIDENCE`** (never a fabricated score).

---

## 18A — Macro data provider (`api/macro_provider.py`)

`MacroDataProvider` Protocol + normalizer. Providers: `SeedDemoProvider`
(default — wraps `EconomicDataRegistry` released observations +
`StandardMacroCalendarProvider` upcoming schedule) and `NullProvider`
(`MACRO_DATA_PROVIDER=none` → every response `available:false`). A real feed
plugs in by adding one class + registering it; **no other code changes**.

`normalize_event()` — canonical `EconomicEvent` shape (event_id, timestamp,
country, currency, event, indicator, category, impact LOW/MEDIUM/HIGH/CRITICAL,
actual, forecast, previous, revised_previous, unit, source, provider, status,
release_timestamp, provenance, metadata). Parses `"225K"`/`"+0.3%"` → float;
**missing fields stay `None`**; malformed records (no name / no time / not a
dict) → dropped.

## 18B — Economic Surprise Engine (`api/surprise_engine.py`)

`evaluate_surprise(indicator, actual, forecast, previous, unit)` — deterministic,
pure. An explicit per-indicator config (`_CFG`) describes `category`,
`higher_is` (positive/negative for the economy), `policy_bias_on_beat`
(HAWKISH/DOVISH), `pct_valid`, `std`. **No universal rule:** a CPI beat →
`direction_bias=NEGATIVE, policy_bias=HAWKISH`; a GDP beat → `POSITIVE`; an
Unemployment beat → `NEGATIVE, DOVISH`; a Jobless-Claims miss → `POSITIVE`.
`normalized_surprise` only when a `std` is configured; `surprise_pct` only when
mathematically valid. States: `POSITIVE_SURPRISE` / `NEGATIVE_SURPRISE` /
`INLINE` / `INSUFFICIENT` / `UNAVAILABLE`. `resolve_indicator()` maps free-text
event names to canon keys.

## 18C — Macro impact  (reused + service)

`macro_intelligence_engine.EconomicSurpriseEngine` maps release → direction /
market implication per family; `MacroFactorGroupingEngine` rolls indicators into
the 5 factor groups with direction / confidence / supporting+conflicting metrics.
The service exposes these as `factor_groups` per currency and as opposing /
supporting factor lists per asset. States are `BULLISH / BEARISH / NEUTRAL /
MIXED / INSUFFICIENT_EVIDENCE`.

## 18D — Currency relative strength  (service over reused engine)

`GET /api/macro/currencies` scores USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD via
`EconomicStrengthEngine` — but only when the provider actually has releases for
that currency (checked against `EconomicDataRegistry.get_releases_as_of`); else
`INSUFFICIENT_EVIDENCE`. Returns score, classification, confidence, direction,
surprise momentum, factor groups, supporting events, and strongest/weakest
rankings. `GET /api/macro/pairs` derives 10 relative-strength pairs
(EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD, GBPJPY, EURJPY, EURGBP)
from `ForexRelativeStrengthEngine` or the currency-score differential.

## 18E — Asset macro context  (`api/macro_service.get_asset`)

`GET /api/macro/assets` — XAUUSD/XAGUSD/USOIL/SPX500/NAS100. **XAUUSD** uses the
dedicated `XAUUSDMacroContextModel` (USD pressure, real-rate proxy, yield
trajectory, inflation support, safe-haven demand, COT). The other four use a
**transparent linear driver rollup** from the USD factor groups with **fixed,
displayed weights** (`method` field explains it) — context, not a forecast.
Returns macro_bias, score, confidence, supporting/opposing factors, evidence
count; `INSUFFICIENT_EVIDENCE` when USD releases are absent.

## 18F — API (`api/routers/macro.py`) — GET-only

| Endpoint | Notes |
| :-- | :-- |
| `GET /api/macro/events` | `window` (all/upcoming/recent), `start`/`end` (ISO), `country`, `currency`, `impact`, `indicator`, `limit` (1–500). Bad window / date / start>end / currency / impact / limit → 422 |
| `GET /api/macro/events/upcoming` · `/recent` | convenience |
| `GET /api/macro/surprises` | scored recent releases, `currency` filter |
| `GET /api/macro/currencies` · `/currencies/{ccy}` | unsupported ccy → **404** |
| `GET /api/macro/pairs` | relative strength |
| `GET /api/macro/assets` · `/assets/{asset}` | unsupported asset → **404** |
| `GET /api/macro/overview` | regime, strongest/weakest, upcoming high-impact, latest surprises, freshness |

Every response: `data_provider`, `provider_is_live`, `provenance`, `available`,
`disclaimer`, `timestamp`. POST/PUT/DELETE → 405. No secret ever appears
(test scans every response for `api_key`/`secret`/`token`/…).

## 18G — React dashboard (`/research/macro`, nav `research.macro`)

`MacroIntelligencePage` — 4 tabs: **Overview** (regime, strongest/weakest
currencies, insufficient-evidence list, upcoming high-impact, latest surprises),
**Economic Calendar** (Time/Ccy/Event/Impact/Actual/Forecast/Previous/Surprise/
Status, filter by currency/impact/text), **Currency Strength** (score, factor
groups with supporting/conflicting metrics), **Asset Macro Context** (bias,
score, drivers, supporting/opposing factors, method). One batched
`Promise.allSettled` fetch (no per-section fan-out), 2-min hidden-paused
refresh, `AbortController`, last-good retained. Reuses `SectionCard` /
`OpsMetric` / `OpsStatusTag`; **no new dependency**. A permanent provenance
banner. Loading / empty / insufficient-data / error states throughout.

## 18H — Gemini macro context (`api/ai_context.py`)

`_macro_context()` adds a **bounded** `macro_intelligence` section to the
allowlisted snapshot: provenance + is_live flag, regime, strongest/weakest
currencies (≤3 each), currencies with insufficient evidence, ≤5 upcoming
high-impact events, ≤5 recent important surprises, asset macro bias. No raw
provider payloads, no full calendar history. `SYSTEM_INSTRUCTION` updated:
macro data is authoritative-when-present, timestamped, possibly incomplete,
possibly demo, **not predictive and never an execution signal** — "Do not turn
a macro bias into a buy/sell instruction." `context_as_prompt_block` still
bounded (raised cap to 16k; a full build is ~7k). The AI module import-graph
still has no execution path (test).

---

## 18I — Reference / screenshot gap audit

Reference supplied: one EdgeFinder-style "Forex Scorecard" screenshot (USDJPY) —
a composite bias gauge + sub-category gauges (Technical Signal, Institutional
Activity/COT, Sentiment Bias, Eco Growth Comparison, Jobs Market Comparison,
Inflation Data Comparison), each Bullish/Bearish/Neutral with an integer score;
row-level "X vs. forecast" comparisons with badges; an "EdgeFinder score over
time" sparkline; per-country Economic Heatmaps (US/EU/UK/JP/CA/AU/NZ/CH);
sidebar sections (Asset Scorecard, Forex Scorecard, Top Setups, COT Data, Crowd
Sentiment, Macro Scanners). Only one screenshot was provided ("just preview, we
can go thru each later") — this audit is intentionally the handoff point.

| Reference element | Status | Layer for the gap |
| :-- | :-- | :-- |
| Economic calendar (Time/Ccy/Event/Impact/Actual/Forecast/Previous) | **implemented** | — |
| Surprise per event (actual vs forecast, per-indicator direction) | **implemented** | — |
| Currency macro score + direction | **implemented** (float −100..100) | — |
| Factor groups (Growth / Inflation / Labor / Rates / Sentiment) | **implemented** as `factor_groups` | — |
| Asset macro context (Gold + generic) | **implemented** | — |
| Strongest / weakest currency ranking | **implemented** | — |
| Insufficient-evidence handling | **implemented** (CHF/CAD/AUD/NZD) | — |
| **Composite integer bias score (−3..+3) per instrument, gauge UI** | **partial** — score exists as a float; no compact integer + gauge | calc (bucketing) + React |
| **Per-instrument "scorecard" with 6 category sub-gauges** | **partial** — data is in `factor_groups`; not laid out as a scorecard | React (+ small calc to normalize category → score/label) |
| **Row-level "X vs. forecast" comparison list inside a scorecard** | **partial** — data in `factor_groups[].supporting/conflicting` and calendar surprises; not a per-category rollup list | API (a `/currencies/{ccy}/scorecard` shape) + React |
| **"Technical Signal" sub-score** | **missing** — pure macro engine has no technicals; TradeLogger has MTF/SMC elsewhere | API (compose from existing MTF engine) + React |
| **"COT Data" / "Crowd Sentiment" as first-class sections** | **partial** — `SENTIMENT_POSITIONING` factor group + `COT_NET_POSITIONING` seed exist; not surfaced as dedicated panels | API + React |
| **"Score over time" sparkline** | **missing** — `MacroIntelligenceSnapshotStore` exists but is not written/surfaced by Stage 18 | data layer (record snapshots) + API + React |
| **Per-country Economic Heatmaps (US/EU/UK/JP/CA/AU/NZ/CH)** | **partial** — `economic_heatmap.EconomicHeatmapEngine` + `/api/intelligence/heatmap` exist (US-centric, 5 categories); not per-country, not in the macro dashboard | API (per-country param) + React |
| **Realized volatility / avg daily move** | **out of scope** — market-data metric, not macro; exists in market snapshot | — |
| **Top Setups / Macro Scanners sidebar** | **unclear / needs reference** | — |
| Real economic data | **missing** — provider is seeded demo | data layer (connect a real feed via `MACRO_DATA_PROVIDER`) |

**Recommendation:** the foundation is complete and correctly layered. The next
iteration (with more screenshots) is a **scorecard composition layer**
(`/api/macro/scorecard/{instrument}` → composite integer bias + category
sub-scores + comparison rows), a **score-over-time** series (start writing
`MacroIntelligenceSnapshotStore` on a schedule + a `/history` endpoint), and
**per-country heatmap** wiring — all additive, no restructuring. And, whenever
available, a real macro data provider.

---

## Validation

| Gate | Result |
| :-- | :-- |
| `tests/test_stage18_macro.py` | **32 passed** |
| Existing macro tests (`test_phase55_macro`, 13× `test_phase56_*`, `test_phase57_surprise_heatmap`) | unchanged, passing |
| Full suite `pytest tests/ -p no:randomly` | **1043 passed, 2 skipped, 0 failed** (baseline 1011/2/0; +32) |
| `npx tsc -b` | clean |
| `npm run build` | clean — 165 modules, 510.10 kB JS / 136.72 kB gzip (chunk-size warning only) |
| Browser — `/research/macro` | loads, "DEMO / SEEDED DATA" banner, 4 tabs, calendar 134 rows, `INSUFFICIENT_EVIDENCE` shown for CHF/CAD/AUD/NZD, GET-only, 0 console errors, 0 exceptions, no body overflow |
| Browser regression | 14 routes (all Workspace / Research / Operations pages) — 0 console errors, 0 exceptions |

## Safety

| Flag | Value |
| :-- | :-- |
| `automation_enabled` | `false` (unchanged) |
| `live_broker_transmission` | `BLOCKED` (unchanged) |
| `execution_orders` count | 335 (unchanged) |
| `mode_counts` | unchanged |
| `open_positions` | 2 (unchanged) |
| execution pipeline / broker adapter / risk gateway touched | **no** |
| Stage 11 cache touched | **no** |
| macro / AI modules bind an execution symbol | **no** (binding + import-graph tests) |

## Data-provider status

`MACRO_DATA_PROVIDER=seed_demo` (default). Realistic *shape*, **not live market
data**; USD/EUR/GBP/JPY only. Set `MACRO_DATA_PROVIDER=none` to force every
response unavailable. A real feed connects by adding one provider class — no
other change.

## Known limitations

- All macro numbers are demo/seeded — clearly labelled everywhere.
- CHF/CAD/AUD/NZD, and every pair involving them, return `INSUFFICIENT_EVIDENCE`.
- "Upcoming" events come from the synthetic `StandardMacroCalendarProvider`.
- No composite scorecard / score-over-time / per-country heatmap yet (§18I).
- Pre-existing `api/routers/positions.py:34` NULL-`tp` bug — untouched.
