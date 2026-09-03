# Phase 66 — Multi-Provider Macro Evidence Layer

```text
commit:        f599ff9
working tree:  clean
pushed:        origin/main
```

Phase 65 gave the macro stack one authoritative provider (FRED/ALFRED) for real
observations, release timestamps and revision vintages. Phase 66 makes the
evidence layer **multi-source, capability-declared, point-in-time correct and
provider-independent** — the Phase-56 scoring engines still ask *what data
exists*, never *which vendor supplied it*.

---

## 1. Provider inventory

| Provider | Capability | Coverage | Status |
| --- | --- | --- | --- |
| **FRED / ALFRED** (`fred`) | observations, release timestamps, revisions, historical | CPI / core CPI / PCE / unemployment / policy rate / GDP / yields — USD/EUR/GBP/JPY full, CAD/AUD/NZD/CHF partial | Live when `MACRO_DATA_PROVIDER=fred` + key (Phase 65, unchanged) |
| **CFTC Commitments of Traders** (`cftc`) | COT positioning, historical | Net non-commercial for GOLD→USD, EUR, GBP, JPY, CAD, CHF, AUD, NZD | **NEW — real, live.** Official US gov Socrata API, **no key**. Enable with `MACRO_COT_PROVIDER=cftc` |
| **Consensus forecast** (`forecast`) | consensus_forecast | — | **Contract only.** `NullForecastProvider` by default → `forecast=None`, surprise `UNAVAILABLE`. No free authoritative feed exists (licensing). |
| **Retail sentiment** (`sentiment`) | retail_sentiment | — | **Contract only.** `NullSentimentProvider` → Sentiment category `INSUFFICIENT_EVIDENCE`. No free redistributable feed. |
| ISM / S&P PMI | pmi | — | **No provider.** Proprietary. `INSUFFICIENT_EVIDENCE`; dependency documented. |

`GET /api/macro/providers` returns the live registry, capability map, per-economy
coverage matrix, conflict list and precedence table. It never returns a secret.

---

## 2. Architecture

```text
        FRED/ALFRED        CFTC COT        Forecast(null)     Sentiment(null)
             │                │                 │                   │
    FredMacroProvider   CftcCotProvider   NullForecastProvider  NullSentimentProvider
             │                │                 │                   │
             └──────── api/providers/registry.py — Capability declarations ───────┘
                                      │
                        api/macro_evidence.ensure_evidence()
                          • hydrate base observation provider
                          • hydrate COT provider (additive)
                          • merge forecasts by (country, metric, period)
                          • detect_conflicts() + source precedence
                          • build per-economy × per-category coverage matrix
                                      │
                     EconomicDataRegistry  (canonical, lookahead-gated)
                                      │
        MacroFactorGroupingEngine / EconomicSurpriseEngine / MacroIntelligenceEngine
                              (Phase 56 — UNCHANGED)
                                      │
              macro_service / macro_scorecard  →  /api/macro/*  →  React
```

`api/macro_provider.ensure_macro_data()` is now a 4-line shim over
`ensure_evidence()`. Consumers are untouched — the response envelope allows
extra keys, so `coverage` / `conflicts` / `providers` / `capabilities` flow
through the existing shapers.

The scoring engines learn nothing about vendors. The **only** engine-adjacent
change is a shaper-level gate in `macro_service.get_currency`: it drops the
`SENTIMENT_POSITIONING` factor group (returns `INSUFFICIENT_EVIDENCE`) when the
registry holds no real `COT_NET_POSITIONING` release for that economy — so the
engine's internal ~238.5k-contract model prior can never surface as a reading
(§16). `MacroFactorGroupingEngine` scoring logic is unchanged.

---

## 3. Forecast implementation

- **Canonical model** — `EconomicForecast` (`api/providers/forecast_provider.py`):
  `provider, source, indicator (canonical metric), country, period, forecast,
  previous, release_timestamp, forecast_timestamp (vintage), retrieved_at, unit,
  n_estimates, consensus_low/high, event_id`. Only fields a real provider
  supplies are populated; nothing is invented.
- **Provider** — default `NullForecastProvider` (returns `[]`). There is no free,
  authoritative, redistributable consensus feed. `MACRO_FORECAST_PROVIDER=<key>`
  + a new module is the extension path; the merge is provider-agnostic.
- **Matching** — `merge_forecasts()` keys on `(country, metric, period)` — the
  registry's own dedup identity. Wrong period / country / **canonical indicator**
  → no merge (a `CORE_CPI` forecast never attaches to a `CPI` release). A
  forecast with no matching release is dropped — a release is never invented.
- **Vintage / lookahead** — `forecast_lookahead_ok()`: in a historical (`as_of`)
  context a forecast is visible only if `forecast_timestamp <= as_of`. A forecast
  with **no** vintage is valid only in the live ("now") context — never
  back-dated. If a real provider cannot supply vintages, that is documented, not
  faked.
- **Surprise restoration** — once a forecast is merged, `evaluate_release_surprise`
  takes its normal scored path; no engine change. Verified for
  actual `>` / `<` / `==` forecast, forecast missing, actual missing.

---

## 4. COT

- **Provider** — `CftcCotProvider` (`api/providers/cftc_provider.py`). Source:
  `publicreporting.cftc.gov` Socrata, Legacy Futures-Only (`6dca-aqww`). Official
  US government, free, **no API key**.
- **Coverage** — one net-non-commercial series per economy:
  GOLD (`088691`)→USD, EURO FX (`099741`)→EUR, BRITISH POUND (`096742`)→GBP,
  JAPANESE YEN (`097741`)→JPY, CANADIAN DOLLAR (`090741`)→CAD,
  SWISS FRANC (`092741`)→CHF, AUSTRALIAN DOLLAR (`232741`)→AUD,
  NZ DOLLAR (`112741`)→NZD. USD-index is deliberately omitted (it would collide
  with GOLD on the `(metric, country, period)` identity).
- **Normalization** — `COTObservation` (report_date, market, asset, country,
  non-commercial long/short/net, commercial long/short, open interest). Also
  registered as `MacroReleaseRecord(metric="COT_NET_POSITIONING", actual=net,
  forecast=None, unit="contracts")` so the existing `SENTIMENT_POSITIONING`
  factor group consumes it unchanged.
- **Report timing** — the `report_date` (a Tuesday) is preserved as the
  observation period. The COT is published the **following Friday 15:30 ET**;
  we derive a conservative `release_timestamp = report_date + 3 days @ 20:30 UTC`
  (≥ 15:30 ET in both DST states). Occasional US-holiday weeks push publication
  to Monday — a documented imprecision, and it always errs *later*, so a report
  is never shown before it was public.
- **Model-prior protection (§16)** — on a successful hydrate the provider replaces
  any existing `COT_NET_POSITIONING` rows (seeded prior or previous hydrate) for
  the covered economies. On an outage it registers nothing and reports
  `PROVIDER_UNAVAILABLE` — the seeded prior is not substituted.
- **Resilience** — bounded timeout, wall-clock budget, 5-min failure backoff,
  6h TTL cache. Startup warm-up primes it when selected.
- **Limitations** — no forecast for positioning (there is none); publication
  timestamp is derived, not reported by the source; disaggregated /
  managed-money breakdown is not used (legacy report only).

---

## 5. Sentiment

- **Provider** — `NullSentimentProvider` (`api/providers/sentiment_provider.py`).
  `SentimentObservation` model is defined (provider, source, instrument,
  timestamp, long/short/net %, methodology) for a future real source.
- **Why null** — OANDA v20 order book needs a funded account; IG / DailyFX client
  sentiment is gated and its terms restrict redistribution. No free authoritative
  feed.
- **Result** — Sentiment category is `INSUFFICIENT_EVIDENCE`. Sentiment is
  **never** inferred from price action or social-media activity.

---

## 6. Conflict handling

- **`detect_conflicts(claims)`** (`api/macro_evidence.py`) — groups claims by
  `(identity, field)`. Values within an absolute tolerance of 0.05 "agree" and
  produce nothing. A material disagreement produces one `CONFLICT` entry naming
  the precedence-selected winner and listing every claim — nothing is averaged,
  nothing is silently chosen.
- **Source precedence** (documented, justified):

  | Rank | Source class |
  | --- | --- |
  | 4 | national statistical agency / central bank, direct (BLS, BEA, Census, Eurostat, ONS, Fed, ECB, BoE, BoJ, CFTC, DoL) |
  | 3 | FRED / ALFRED — the Federal Reserve's mirror of official series |
  | 2 | OECD-harmonised cross-country series |
  | 1 | any other named aggregator |
  | 0 | unknown |

- **Different series, same name** — the merge keys on the canonical metric, so a
  `CORE_CPI` figure never merges into a `CPI` series even though both display as
  "CPI". Incompatible series stay separate.
- **Live conflicts today** — none. FRED is the sole observation source and CFTC
  the sole COT source, so the mechanism is exercised only by tests and by the
  forecast-`previous` vs registry-`previous` path. When a second observation
  provider is added, conflicts surface automatically as `provider_state:
  CONFLICT` + a red provenance banner + entries in the Providers panel.

---

## 7. Data quality / freshness

Evidence states, per capability × economy:

| State | Meaning |
| --- | --- |
| `LIVE` | real provider data, fresh |
| `LIVE_STALE` / `STALE` | real data, past its TTL, refresh pending — disclosed, not hidden |
| `SEED_DEMO` | seeded shape, not real (default) |
| `INSUFFICIENT_EVIDENCE` | no source for this field — **not zero** |
| `PROVIDER_UNAVAILABLE` | a configured live provider is down — last-good shown where safe, seed **never** substituted |
| `NONE` | `MACRO_DATA_PROVIDER=none` |
| `CONFLICT` | two sources materially disagree |

Provider outage behaviour is the Phase-65 contract, intact:
`EconomicDataRegistry._PROVIDER_MANAGED` blocks the demo seed when a real
provider owns the registry; `macro_scorecard` returns `available: false,
state: PROVIDER_UNAVAILABLE` rather than seeded numbers.

---

## 8. Evidence / provenance traceability

Every live observation keeps `source` (e.g. `FRED:CPIAUCSL`, `CFTC:088691`),
`source_timestamp` (retrieved_at) and `release_timestamp`. The user can trace:

```text
composite score            /api/macro/scorecard/USD → composite_score
   → category score              → categories[].score  (growth / jobs / inflation / cot)
      → indicator row                 → categories[].indicators[]  (actual / forecast / previous / surprise)
         → underlying release              → EconomicDataRegistry record
            → provider / source                 → source = "FRED:CPIAUCSL" / "CFTC:088691"
               → timestamp                            → release_timestamp (UTC), source_timestamp
```

`GET /api/macro/providers` exposes the coverage matrix and per-provider health
(state, last success/failure, latency, backoff, errors) — read-only, no secret.

---

## 9. Lookahead — exact tests

`tests/test_phase66_lookahead.py`:

| Case | Test |
| --- | --- |
| future release excluded | `test_future_release_excluded` (as-of before `release_timestamp` → 0 rows) |
| exact release included | `test_exact_release_included` (as-of == `release_timestamp` → 1 row) |
| retrieved-after-but-released-before valid | `test_retrieved_after_but_released_before_is_valid` (`source_timestamp` 2026-10-01, `release_timestamp` 2026-09-11, as-of 2026-09-15 → visible) |
| forecast vintage excluded when future | `test_forecast_vintage_excluded_when_future` (`forecast_timestamp` after as-of → not merged) |
| forecast vintage included when known | `test_forecast_vintage_included_when_known` |
| COT future report excluded | `test_cot_future_report_excluded` (Tue report, as-of before Fri 20:30 UTC → 0; after → 1) |

Plus `tests/test_phase66_cftc_cot.py::test_lookahead_future_report_excluded` /
`test_lookahead_earlier_report_included` and the Phase-65 FRED lookahead suite,
still green.

---

## 10. Tests

```text
1177  passed
   6  skipped   (incl. test_phase66_cftc_smoke — RUN_LIVE_SMOKE gate;
                 test_phase66_forecast_smoke — CREDENTIALS NOT CONFIGURED)
   0  failed
```

`pytest tests/ -p no:randomly` — 318s. Phase-65 baseline was 1107 passed / 4
skipped; Phase 66 adds ~68 offline tests + 2 gated live smokes.

New Phase-66 files (all offline, HTTP monkeypatched):
`test_phase66_provider_registry.py`, `test_phase66_cftc_cot.py`,
`test_phase66_forecast.py`, `test_phase66_conflict.py`,
`test_phase66_surprise_restoration.py`, `test_phase66_evidence_layer.py`,
`test_phase66_lookahead.py`, `test_phase66_safety.py`,
`test_phase66_cftc_smoke.py` (skipped), `test_phase66_forecast_smoke.py` (skipped).

---

## 11. Browser QA

`serve_dist.py` (static production `dist` + `/api` proxy to a dedicated uvicorn
on :8021), headless Chrome via CDP, run with `MACRO_DATA_PROVIDER=fred` +
`MACRO_COT_PROVIDER=cftc` and an empty key (offline → PROVIDER_UNAVAILABLE /
PENDING states rendered). Teardown kills only the spawned PIDs — no
`taskkill /IM`.

```text
routes:              22 × 3 resolutions = 66 page loads
resolutions:         1280×720 / 1600×900 / 1920×1080
console errors:      0
exceptions:          0
positive overflow:   0   (−15 = scrollbar gutter, expected)
macro tabs walked:   7   (Scorecard, Heatmap, Overview, Calendar, Currency
                          Strength, Asset Macro Context, Providers & Coverage)
failed interactions: 0   (all 7 tab clicks succeeded, Providers panel rendered)
FINDINGS:            0
```

---

## 12. Performance

Warm p50, seed_demo default (`TestClient`, 15 samples, same machine back-to-back):

```text
endpoint                     pre-Phase-66     Phase 66
/api/macro/overview          ~18 ms           ~28 ms   (+10 ms — coverage-matrix
                                                        build in the fan-out)
/api/macro/scorecard/USD     ~600 ms          ~560 ms  (unchanged — pre-existing
                                                        engine cost, within noise)
/api/macro/currencies        ~17 ms           ~12 ms   (noise)
/api/macro/providers         —                ~9 ms    (new)
```

The default (seed_demo) path adds one `MacroProviderRegistry.discover()` +
per-economy coverage-matrix build per `ensure_evidence()` — pure in-memory, no
network, no DB, no new dependency. `ensure_evidence()` itself is ~0.4 ms warm.
The Phase-62 DB pool / cache infrastructure is untouched. Live providers keep
the Phase-65 bounded-timeout / budget / backoff / TTL contract and are primed at
startup; the UI stays responsive if a provider is slow (each hydrate is
budget-capped and never on the request's critical path after the first).

---

## 13. Safety

```text
LIVE_AUTOMATION_ENABLED    = False   (unchanged)
LIVE_BROKER_TRANSMISSION   = "BLOCKED"   (unchanged)
Execution files modified   = 0
Strategy Contract SHA-256  = 7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76  (unchanged)
```

`tests/test_phase66_safety.py` verifies: `/api/health` unchanged before & after
every new endpoint; none of `api/providers/{registry,fred_provider,cftc_provider,
forecast_provider,sentiment_provider}` or `api/macro_evidence` imports
`execution_pipeline` / `broker_adapter` / `risk_gateway` / `reconciliation`;
`/api/macro/providers` never echoes a `FRED_API_KEY`; no hardcoded credential in
source. `execution_pipeline.py`, `broker_adapter.py`, `risk_gateway.py`,
reconciliation, webhook security, order systems, `database.py`, the DB pool and
the Phase-62 perf infra are untouched. `MacroFactorGroupingEngine` scoring logic
is untouched.

---

## 14. Git

```text
commit:        f599ff9
working tree:  clean
pushed:        origin/main
```

Files — **new:** `api/providers/registry.py`, `api/providers/forecast_provider.py`,
`api/providers/sentiment_provider.py`, `api/providers/cftc_provider.py`,
`api/macro_evidence.py`, `frontend/src/components/macro/MacroProviders.tsx`,
`docs/PHASE_66_MACRO_EVIDENCE.md`, `tests/test_phase66_*.py` (10).
**modified:** `api/macro_provider.py`, `api/providers/fred_provider.py` (KEY/CAPABILITIES
only), `api/macro_service.py` (COT-prior gate), `api/routers/macro.py`,
`api/schemas.py` (§17), `api/main.py` (CFTC warm-up), `api/ai_context.py`,
`frontend/src/types/macro.ts`, `frontend/src/api/macro.ts`,
`frontend/src/components/macro/MacroViews.tsx`,
`frontend/src/pages/MacroIntelligencePage.tsx`, `.env.example`.

---

## 15. Remaining gaps

**PROVIDER LIMITATION**
- CFTC legacy report only — no disaggregated / managed-money breakdown.
- CFTC has no explicit publication timestamp; `release_timestamp` is a
  conservative derivation (Fri 20:30 UTC), imprecise on holiday weeks.
- FRED cross-country GDP / labor coverage is partial for CAD/AUD/NZD/CHF (Phase 65).

**IMPLEMENTATION LIMITATION**
- Conflict detection is wired for the forecast-`previous` vs registry-`previous`
  path and unit-tested; a second live observation provider would exercise the
  `actual` path end-to-end.
- Forecast merge only sets `forecast` / fills a missing `previous`; it does not
  reconcile `release_timestamp` between a calendar provider and FRED.

**LICENSING / ACCESS LIMITATION**
- No free authoritative **consensus forecast** feed → surprise stays
  `UNAVAILABLE` for FRED indicators. `NullForecastProvider` + extension hook.
- No free redistributable **retail sentiment** feed → Sentiment category
  `INSUFFICIENT_EVIDENCE`.
- **ISM / S&P PMI** are proprietary → `INSUFFICIENT_EVIDENCE`.

**FUTURE ENHANCEMENT**
- A release-calendar provider (scheduled upcoming events with expected times).
- COT change-vs-prior-week and percentile-of-range context in the scorecard.
- Per-viewer "explain this score" drill-down surfacing the full trace from §8.

---

## STOP

Phase 66 delivered a provider-independent, capability-declared, point-in-time
correct multi-source evidence layer under the unchanged Phase-56/64 scoring
engines. CFTC COT is real and live. Forecast and sentiment ship as honest
contracts that return `INSUFFICIENT_EVIDENCE` until a source is configured — a
provider that cannot supply a field never fabricates one, a provider that is
down never falls back to seeded data, and two sources that disagree surface a
`CONFLICT` rather than a clean number.
