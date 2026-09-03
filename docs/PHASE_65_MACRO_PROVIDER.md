# Phase 65 — Production Macro Data Provider (FRED)

*Connects the Phase-64 macro intelligence layer to authoritative real-world data
(FRED / ALFRED) without changing the scoring engine, breaking the seed-demo
default, or weakening lookahead / provenance / safety. The FINAL RULE applies:
real data beats visual completeness — a field with no authoritative source
stays `INSUFFICIENT_EVIDENCE`.*

---

## 1. Provider selected — FRED / ALFRED

**FRED** (Federal Reserve Economic Data, St. Louis Fed) with its **ALFRED**
vintage database.

| Why | Detail |
| :-- | :-- |
| Authoritative | Published by the Federal Reserve; official / OECD-sourced series |
| Access | Free API key, instant, no cost, no licensing barrier — `https://fred.stlouisfed.org/docs/api/api_key.html` |
| Real release timestamps | ALFRED `realtime_start` = the date a value first became public — a genuine release timestamp, not the observation period |
| Real revisions | ALFRED returns every vintage → `initial_actual`, `revised_actual`, `revision_delta`, `revision_timestamp` are real |
| Cross-country | OECD-hosted series give consistent CPI / unemployment / policy-rate / GDP for the G10 |
| Test-friendly | Deterministic historical data; the test suite mocks the HTTP layer entirely (no key needed) |

### Honest limitations (reported, never fabricated)

| Missing | Consequence |
| :-- | :-- |
| **Consensus forecast** — FRED has none | `forecast = None`; the surprise engine returns `UNAVAILABLE` for every FRED indicator. Category scoring uses the engine's absolute-level + trend logic instead. This is a real reduction in signal vs the seeded dataset and is surfaced in the UI ("no consensus forecast from this source"). |
| **CFTC COT positioning** | COT category stays `INSUFFICIENT_EVIDENCE` |
| **ISM PMI** (proprietary) | Those growth sub-indicators are absent |
| **Retail sentiment / technical** | Not macro-provider data → `INSUFFICIENT_EVIDENCE` (unchanged from Phase 64) |
| **Intraday release time** | ALFRED gives a *date*, not a timestamp. Release time is set to `13:30Z` (a conservative standard-AM-release proxy). Documented; same-day lookahead is therefore slightly conservative. |

---

## 2. Architecture

```
FRED API (api.stlouisfed.org)
        │  httpx? no — requests (existing dep). 8-way ThreadPoolExecutor,
        │  hard wall-clock budget, per-call timeout, failure backoff.
        ▼
api/providers/fred_provider.py   FredMacroProvider
        │  _fetch_series → ALFRED vintages
        │  _records_from_series → collapse vintages to one canonical record
        │                          per observation period (first-print + latest)
        ▼
macro_intelligence_engine.MacroReleaseRecord      ← canonical model (unchanged)
        │  EconomicDataRegistry.register_release()
        ▼
EconomicDataRegistry  ← the SAME lookahead-gated store the seed dataset uses.
        │  get_releases_as_of(as_of=...)   release_timestamp <= as_of
        ▼
MacroFactorGroupingEngine / EconomicSurpriseEngine   ← UNCHANGED
        ▼
api/macro_service.py  ·  api/macro_scorecard.py       ← UNCHANGED logic;
        │                                                only provenance +
        │                                                provider-outage gating
        ▼
/api/macro/*  →  React (Scorecard / Heatmap / …)
```

The scoring layer never learns which vendor supplied the data. Swapping FRED for
another provider = one class + `MACRO_DATA_PROVIDER`.

### Consumer changes (minimal)

| File | Change |
| :-- | :-- |
| `api/macro_provider.py` | registered `"fred"`; added `ensure_macro_data()` — called by every macro read, triggers a TTL-guarded hydrate, returns provenance. Never raises. |
| `api/macro_service.py` | `_provider_meta()` now delegates to `ensure_macro_data()`. |
| `api/macro_scorecard.py` | `_provenance()` delegates to `ensure_macro_data()`; `get_scorecard` / `get_country_heatmap` return `PROVIDER_UNAVAILABLE` (not seeded fallback) when a live provider is configured but has no data. |
| `api/main.py` | startup warm-up hydrates FRED (budget-bounded, guarded) so the first macro request is fast and a broken provider degrades before a user sees it. |
| `macro_intelligence_engine.py` | (a) `EconomicSurpriseEngine.evaluate_release_surprise` incomplete-data path now returns the **same key set** as the scored path (`z_score`, `family`, `unit`, …) — a genuine compatibility fix: FRED supplies real actuals with no forecast, and the factor engine did `s["z_score"]` unconditionally → `KeyError`. Zero logic change. (b) `EconomicDataRegistry._PROVIDER_MANAGED` flag — when a real provider owns the registry the seeded canonical dataset is never auto-loaded. |
| `api/ai_context.py` | unchanged — the existing `_scorecard_context()` already carries whatever the (now possibly live) scorecard produces; the system instruction ("macro is context, never an execution signal") is unchanged. |

---

## 3. Data coverage (mapped series)

`X` = a FRED series is mapped. Actual availability is confirmed only by the live
smoke test — a mapped series that 404s is skipped and recorded in
`provider_status.series_errors`, never faked.

| Economy | Growth (GDP) | Jobs (unemp.) | Inflation (CPI/core/PCE) | Rates (policy/2Y/10Y) | COT | Sentiment |
| :-- | :--: | :--: | :--: | :--: | :--: | :--: |
| **US (USD)** | X | X (+NFP, claims) | X (CPI, core CPI, PCE, core PCE) | X (target + 2Y + 10Y) | — | — |
| **EU (EUR)** | X | X | X (HICP) | X (ECB DFR) | — | — |
| **UK (GBP)** | X | X | X | X | — | — |
| **JP (JPY)** | X | X | X | X | — | — |
| **CA (CAD)** | — | X | X | X | — | — |
| **AU (AUD)** | — | X | X | X | — | — |
| **NZ (NZD)** | — | X | X | — | — | — |
| **CH (CHF)** | — | X | X | X | — | — |

Growth extras (RETAIL_SALES, CONSUMER_CONF) are mapped for USD only. ISM PMI is
not on FRED.

---

## 4. Data states

| State | Meaning | UI |
| :-- | :-- | :-- |
| `SEED_DEMO` | `MACRO_DATA_PROVIDER` unset / `seed_demo` (**default**) | amber "Demo / seeded data" banner |
| `LIVE` | FRED configured + hydrated within TTL | green "Live provider data" + series/coverage count + last-updated |
| `LIVE_STALE` | FRED hydrated but the 6h cache lapsed and a refresh is pending | green, "stale — refresh pending" |
| `PROVIDER_UNAVAILABLE` | FRED configured but the last hydrate failed (timeout / 4xx / 5xx / no data) | **red** "Provider temporarily unavailable" — explicitly *not* "insufficient evidence", and **seeded data is not shown in its place** |
| `INSUFFICIENT_EVIDENCE` | a specific category/country/instrument has no authoritative source | per-card, unchanged from Phase 64 |
| `NONE` | `MACRO_DATA_PROVIDER=none` | red "no data provider configured" |

`INSUFFICIENT_EVIDENCE` (no evidence) and `PROVIDER_UNAVAILABLE` (transient
outage) are visually and semantically distinct (§20).

---

## 5. Lookahead verification

Every read still flows through `EconomicDataRegistry.get_releases_as_of(as_of=)`
which excludes `release_timestamp > as_of`. For FRED, `release_timestamp` is the
ALFRED first-print date (`13:30Z`), **not** the observation period.

Tests (`tests/test_phase65_fred_provider.py`):

| Test | Proves |
| :-- | :-- |
| `test_lookahead_future_release_excluded` | July CPI (released 2026-08-12) is invisible at `as_of=2026-08-11`, visible at exactly `2026-08-12T13:30Z` |
| `test_lookahead_observation_period_past_but_release_future_excluded` | **the classic trap** — August data released 2026-09-15 is NOT visible on 2026-09-03 just because its period is "August" |
| `test_lookahead_earlier_release_included` | all historical prints visible far in the future |
| `test_revision_preserves_initial_value` | a revised June CPI keeps `initial_actual` (first print) and `revision_timestamp` |

Plus the existing `test_phase56_lookahead` / `test_phase64` lookahead suites
still pass unchanged.

---

## 6. Provenance

Every live `MacroReleaseRecord` carries:

| Field | Source |
| :-- | :-- |
| `source` | `FRED:<series_id>` (the source identifier) |
| `source_timestamp` | retrieved-at (UTC ISO) |
| `release_timestamp` | ALFRED `realtime_start` of the first print, `…T13:30:00Z` |
| `revision_timestamp` | ALFRED `realtime_start` of the latest vintage (if revised) |
| `period` | observation period, `YYYY-MM` |
| `unit` | canonical unit label (`%`, `k`, `index`, …) |
| `initial_actual` / `revised_actual` / `revision_delta` | vintage diff |

The response envelope carries `provider_state` + `provider_status` (coverage
map, per-series errors, hydrated age, cache TTL). The React `ProvenanceBanner`
shows provider, live/demo/outage state, coverage count, last-updated, and the
forecast caveat.

---

## 7. Revision handling

FRED/ALFRED exposes full vintages. `_records_from_series` groups observation
rows by period; the earliest `realtime_start` = first print (`initial_actual` +
`release_timestamp`), the latest ≤ today = the current value (`actual`). If they
differ → `revision_status="REVISED"` with `revised_actual` / `revision_delta` /
`revision_timestamp`. **The originally-known value is preserved** — a revised
number is never presented as what was known at first print.

Bounded: only the most recent 6 periods per metric are registered (the engine
needs current + short history; this caps registry size).

---

## 8. Performance

Macro endpoints, warm p50, in-process TestClient (seed_demo default):

| Endpoint | Phase 64 | Phase 65 | Δ |
| :-- | --: | --: | --: |
| `/api/macro/overview` | 11.0 ms | 12.3 ms | +1 ms (env noise) |
| `/api/macro/currencies` | 3.0 ms | 2.8 ms | — |
| `/api/macro/scorecard/USD` | 258 ms | 243 ms | — (pre-existing engine cost) |
| `/api/macro/heatmap/USD` | 1.7 ms | 1.5 ms | — |
| `/api/macro/scorecard/USD/history` | 257 ms | 243 ms | — |
| `/api/macro/events` | 7.0 ms | 5.2 ms | — |

No regression on the default path — `ensure_macro_data()` is a dict return for
seed_demo.

**FRED path:** hydration is 8-way parallel with a **25 s wall-clock budget** and
a **5-minute failure backoff**. Measured: a broken/slow provider returns the
first macro request in ≤ ~3.4 s (budget), then every request for 5 min is
instant (~0.4 s = the scorecard engine, no HTTP). A healthy hydrate is a one-off
(cached 6 h) and is primed in the startup warm-up.

*(Before the budget/backoff fix a broken provider blocked macro requests for
120 s+ — caught in QA, fixed, tested: `test_broken_provider_backs_off`,
`test_hydrate_respects_wall_clock_budget`.)*

---

## 9. Tests

```
pytest tests/ -p no:randomly
1107 passed
4 skipped        (1 = the FRED live smoke test — no credentials configured)
0 failed
~80–130 s typical
```

New: `tests/test_phase65_fred_provider.py` (29 tests — normalization, country/
indicator mapping, numeric parsing, vintage collapsing, revisions, 4× HTTP
failure modes, timeout, malformed JSON, partial coverage, 3× lookahead,
provenance, scoring flow, incomplete-data key-set fix, provider backoff,
wall-clock budget, seed-demo default preserved, `none` provider, no-seed-fallback
on outage, no execution side effect, no execution import, no key in source) +
`tests/test_phase65_fred_smoke.py` (live smoke — **skipped, no credentials**).

---

## 10. Browser QA

Headless Chrome / CDP, production build:

```
Full route regression : 19 routes × (1280×720 / 1440×900 / 1920×1080) = 66 loads
                        0 console errors · 0 uncaught exceptions · 0 overflow
                        command palette + keyboard shortcuts working

Macro workflow        : 1920×1080 / 1600×900 / 1280×720
                        gauge renders · 6 category cards · DEMO/SEEDED banner shown
                        INSUFFICIENT_EVIDENCE shown for Technical/Sentiment
                        instrument switch USD→EUR→USDJPY : 0 errors
                        heatmap : 17 US indicator rows, Ccy-impact + Equity-impact
                        AUD (no data) → INSUFFICIENT_EVIDENCE
                        0 horizontal overflow at every resolution
                        ISSUES: 0
```

`tsc -b` clean. `npm run build` clean (macro chunk 33.8 kB / 8.5 kB gzip, lazy —
no chunk-size warning).

Provenance-banner states exercised: `SEED_DEMO` (default, amber),
`PROVIDER_UNAVAILABLE` (fred + bad key → red, "not insufficient evidence", no
seed fallback) — both render correctly.

---

## 11. Safety

```
LIVE_AUTOMATION_ENABLED   = False        (verified via /api/health before & after)
LIVE_BROKER_TRANSMISSION  = "BLOCKED"    (verified before & after)
Execution modules modified = NONE        (execution_pipeline / broker_adapter /
                                          risk_gateway / reconciliation untouched)
Contract SHA-256          = 7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76  (unchanged)
```

- `test_provider_has_no_execution_side_effect`, `test_provider_module_imports_no_execution_module`.
- `test_no_api_key_committed_in_source` — the provider reads the key only from
  the environment; `.gitignore` covers `.env` / `.env.local` / `.env.*.local` /
  `.env.production`; the key never appears in a response, a log, or the bundle.
- Phase 62 DB pool / caches / warm-up / code-split — untouched.
- Historical holdout baseline (N=82, E[R]=+0.637R) and dataset isolation — no
  test modified, full suite green.

---

## 12. Git

```
commit:        <filled on commit>
working tree:  CLEAN
```

---

## 13. Remaining gaps

| Gap | Type |
| :-- | :-- |
| **No consensus forecast** for FRED indicators → surprise dimension unavailable, category scoring is level+trend only | **DATA PROVIDER LIMITATION** — needs a calendar source with consensus (e.g. a paid economic-calendar API) added as a *second* provider that fills only `forecast`. |
| **COT** stays `INSUFFICIENT_EVIDENCE` | **DATA PROVIDER LIMITATION** — a CFTC COT feed (the CFTC publishes it; a dedicated provider class could add it). |
| **ISM PMI** absent | **DATA PROVIDER LIMITATION** — proprietary; not on FRED. |
| **Retail sentiment / Technical** categories | **DATA PROVIDER LIMITATION** — unchanged from Phase 64; not macro-provider data. |
| **CAD/NZD GDP**, some rate series | **DATA PROVIDER LIMITATION** — not all G10 GDP/rate series are on FRED with a clean YoY transform; mapped where reliable. |
| Intraday release time | **IMPLEMENTATION LIMITATION** — ALFRED gives a date; release time is a conservative `13:30Z` proxy. A per-indicator release-time table would refine same-day lookahead. |
| Multi-provider merge (FRED actuals + calendar forecasts + CFTC COT) | **FUTURE ENHANCEMENT** — the provider abstraction supports it; a `CompositeProvider` would layer sources by field. |
| Vintage persistence to DB | **FUTURE ENHANCEMENT** — vintages are collapsed in-memory (6 periods/metric). A `macro_releases` table would keep full history across restarts. |

---

## STOP

Real, authoritative macro data now flows through the Phase-64 system when
`MACRO_DATA_PROVIDER=fred` + `FRED_API_KEY` are set. Default is unchanged
(`seed_demo`). No fabrication: no forecast is invented, no model prior is shown
as an observation, an outage is `PROVIDER_UNAVAILABLE` not a `0`, and demo data
is never shown in place of live data. Scoring engine, execution safety, and
Phase 62 performance infra untouched.
