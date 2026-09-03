# Phase 64 — EdgeFinder-Style Macro Intelligence

*Functional build. The EdgeFinder screenshots (`docs/reference/photo_*.jpg`)
were treated as a product reference — the underlying data architecture,
calculations and scores were reproduced over TradeLogger's existing engines,
not the visuals. No fabricated data. No execution capability. Macro stays
read-only context.*

---

## 1. Implementation summary

Extended the Phase-56 macro stack into an EdgeFinder-style scorecard system.
**No new calculation engine was written** — `api/macro_scorecard.py` is a thin
shaper over `MacroIntelligenceEngine` / `MacroFactorGroupingEngine` /
`EconomicSurpriseEngine` / `MacroIntelligenceSnapshotStore`.

Delivered:

- **Composite macro bias + gauge** per instrument (`macro_score` → integer gauge
  −10..10 + VERY BULLISH…VERY BEARISH label).
- **6-category scorecard** — Technical / COT / Sentiment / Growth / Jobs /
  Inflation. Growth/Jobs/Inflation/COT map to real factor groups with
  per-indicator Actual / Forecast / Previous / Surprise / date / family-specific
  direction. **Technical and retail-Sentiment have no macro provider → they
  render `INSUFFICIENT_EVIDENCE` with a stated `next_dependency`, never a
  number.**
- **Score history** from `MacroIntelligenceSnapshotStore` — one immutable
  snapshot is recorded per instrument at most hourly when its scorecard is
  viewed. Honest `NO_HISTORY` empty state; **no synthetic history**.
- **Per-country economic heatmap** (US / EU / GB / JP + CA/AU/NZ/CH/CN →
  `INSUFFICIENT_EVIDENCE`) with deterministic **currency-impact vs
  equity-impact** interpretation per indicator (a hawkish inflation surprise
  supports the currency but pressures equities).
- **Cross-instrument ranking** (`/api/macro/scorecard`) and FX-pair categories
  computed as *base economy − quote economy* (needs both legs — a missing leg
  is `INSUFFICIENT_EVIDENCE`, not silently neutral).
- **AI context** extended with a bounded scorecard summary; system instruction
  unchanged ("macro is context, never an execution signal").

---

## 2. Screenshot capability mapping

| EdgeFinder capability | TradeLogger implementation | Status | Evidence / data source |
| :-- | :-- | :-- | :-- |
| Composite bias score + gauge (Asset/Forex Scorecard) | `macro_scorecard.get_scorecard().composite_score` / `.gauge` ← `MacroIntelligenceEngine.evaluate_macro_context` | **Implemented** | seed_demo (USD/EUR/GBP/JPY + pairs + XAUUSD) |
| 6-category scorecard | `.categories[]` ← `MacroFactorGroupingEngine` (GROWTH/INFLATION/LABOR/SENTIMENT_POSITIONING) + Technical/Sentiment stubs | **4 of 6 evidence-backed**; Technical + retail-Sentiment = `INSUFFICIENT_EVIDENCE` | seed_demo |
| Category score + gauge (donut) | `category.score` / `.gauge`; `<Gauge>` SVG component | **Implemented** | seed_demo |
| Actual / Forecast / Previous / Surprise per indicator | `category.indicators[]` ← `EconomicSurpriseEngine.evaluate_release_surprise` | **Implemented** | seed_demo |
| Family-specific interpretation (hot CPI = hawkish; weak NFP = dovish) | engine `direction` field + `_impact_direction()` for the heatmap | **Implemented + tested** | deterministic rules |
| Score-over-time chart | `.get_scorecard_history()` ← `MacroIntelligenceSnapshotStore` + `<ScoreHistory>` bars | **Implemented** (store was empty; now accumulates) | real recorded snapshots only |
| Per-country Economic Heatmap (US/EU/UK/JP/CA/AU/NZ/CH) | `.get_country_heatmap()` + `<MacroHeatmap>` | **US/EU/GB/JP implemented; CA/AU/NZ/CH/CN = `INSUFFICIENT_EVIDENCE`** | seed_demo / no releases |
| Currency vs Stocks impact columns | `indicator.currency_impact` / `.equity_impact` via `_impact_direction()` | **Implemented + tested** | deterministic rules |
| Cross-asset / currency context | `.get_scorecard_list().ranked` + FX-pair base−quote categories | **Implemented** | seed_demo |
| Top Setups grid (all instruments ranked) | `/api/macro/scorecard` ranked list | **Implemented (data)**; compact grid UI deferred | seed_demo |
| COT report / history, Retail Sentiment history, Geo-risk, weekly calendar grid | COT surfaced inside the COT category; calendar in existing `/api/macro/events` | **Out of scope** this phase | — |

---

## 3. Backend changes

| File | Change |
| :-- | :-- |
| `api/macro_scorecard.py` (**new**, ~430 lines) | Shaper: `get_scorecard`, `get_scorecard_list`, `get_scorecard_history`, `record_scorecard_snapshot` (hourly-deduped), `get_country_heatmap`, `get_heatmap_index`. No engine logic — calls `macro_intelligence_engine`. Guards the engine's model-prior fallbacks so a category with 0 releases is `INSUFFICIENT_EVIDENCE`, not a fabricated score. |
| `api/routers/macro.py` | +5 GET endpoints: `/scorecard`, `/scorecard/{instrument}`, `/scorecard/{instrument}/history`, `/heatmap`, `/heatmap/{country}`. 404 on unsupported instrument/country; 422 on bad `limit`. `/scorecard/{instrument}` records a snapshot best-effort. |
| `api/schemas.py` | Section 16 — `MacroScorecard*` / `MacroHeatmap*` response models (extend `_MacroEnvelope`, so provenance is mandatory). |
| `api/ai_context.py` | `_scorecard_context()` — bounded per-instrument composite + category scores added to the macro block. Context stays capped at 16 000 chars. |

**No execution / broker / risk file touched.** `macro_scorecard` imports only
`macro_intelligence_engine`, `economic_heatmap`, `api.macro_provider`.

---

## 4. Frontend changes

| File | Change |
| :-- | :-- |
| `components/macro/Gauge.tsx` (**new**) | Compact semicircular SVG bias gauge (−10..10 → needle angle); no chart library; dimmed + needle-less for `INSUFFICIENT_EVIDENCE`. |
| `components/macro/MacroScorecard.tsx` (**new**) | Instrument selector (10 instruments), composite panel (gauge + bias + sub-scores + score-history bars), 6 category cards with expandable indicator tables, provenance/disclaimer. |
| `components/macro/MacroHeatmap.tsx` (**new**) | Country selector (dims no-data economies), aggregate row, per-indicator table with Ccy-impact / Equity-impact columns. |
| `lib/useMacroScorecard.ts` (**new**) | `useMacroScorecard` (one `allSettled` batch: scorecard + history; refetch on instrument change) and `useMacroHeatmap`. AbortController + disposed guard + last-good. |
| `pages/MacroIntelligencePage.tsx` | Two new tabs — **Scorecard** (now the default) and **Economic Heatmap** — alongside the existing Overview / Calendar / Currency Strength / Asset Macro Context. |
| `api/macro.ts`, `types/macro.ts` | 4 typed client fns + response types. |

Design system: reuses existing primitives (`SectionCard`, `OpsMetric`,
`OpsStatusTag`, `OpsUnavailable`) and tokens; the only new primitive is `Gauge`.
Macro page chunk 15 kB → 33 kB (8 kB gzip), lazy-loaded — Phase 62 code-split
preserved.

---

## 5. Data model

```
scorecard(instrument)
├── composite_score  (-100..100, from MacroIntelligenceEngine)
├── gauge            (round(score/10), clamped -10..10)
├── bias             (VERY BULLISH / BULLISH / NEUTRAL / BEARISH / VERY BEARISH)
├── state            (OK | PARTIAL | INSUFFICIENT_EVIDENCE | UNSUPPORTED)
├── sub_scores       {growth, inflation, jobs, cot}
└── categories[6]
    ├── category      (technical | cot | sentiment | growth | jobs | inflation)
    ├── score, gauge, direction   (null + INSUFFICIENT_EVIDENCE when no source)
    ├── supporting[] / conflicting[]  (engine confluence notes)
    └── indicators[]
        ├── name, family, unit
        ├── actual, forecast, previous
        ├── surprise = actual − forecast,  z_score = surprise / std
        ├── surprise_state, direction (FAMILY-SPECIFIC), implication
        └── release_time, freshness

heatmap(country)
├── aggregate_score / aggregate_direction
├── categories[]  (growth / inflation / jobs / cot per that economy)
└── indicators[]
    ├── actual / forecast / previous / surprise / release_time
    ├── currency_impact   (strong economy / hawkish = bullish the currency)
    └── equity_impact     (growth strength = bullish; hot inflation = bearish)

history(instrument)  — from macro_intelligence_snapshots table
└── points[]  (chronological ASC)
    ├── timestamp, composite_score, direction
    ├── growth / inflation / jobs / cot
    └── fingerprint  (SHA-256 of the recorded payload)
```

Surprise interpretation is **deterministic and family-specific** (engine
`EconomicSurpriseEngine.evaluate_release_surprise`): INFLATION beat → hawkish;
LABOR (NFP/ADP) miss → dovish; LABOR inverted (unemployment/claims) beat →
labor softening; GROWTH beat → expansionary. Verified in
`test_surprise_interpretation_is_family_specific`.

---

## 6. Data availability

| | Instruments / countries | Notes |
| :-- | :-- | :-- |
| **Real data** | none — no live provider configured | `MACRO_DATA_PROVIDER` unset |
| **Seeded / demo data** (`provenance: "seed_demo"`, `provider_is_live: false`) | Scorecard: USD, EUR, GBP, JPY, XAUUSD, EURUSD, GBPUSD, USDJPY, EURJPY, GBPJPY. Heatmap: US (17 releases), EU / GB / JP (3–4 each) | UI shows a permanent "DEMO / SEEDED DATA" banner |
| **Insufficient evidence** | Scorecard: CAD, AUD, NZD, CHF. Heatmap: CAD, AUD, NZD, CHF, CNY. Categories: Technical + retail-Sentiment (all instruments); COT/Jobs for economies without those releases | Each returns `state: INSUFFICIENT_EVIDENCE` + `next_dependency` |
| **Future provider requirements** | (1) real economic-calendar feed behind `MacroDataProvider` → `provider_is_live: true`, `provenance: "live"`; (2) a macro-technical feed (chart-trend + seasonality) for the Technical category; (3) a retail/crowd positioning feed for the Sentiment category; (4) COT / PMI / labour coverage for EUR/GBP/JPY and the other G10 economies | Architecture already supports (1) with one provider class — no app change |

---

## 7. Safety verification

```
LIVE_AUTOMATION_ENABLED       = False        (via /api/health, unchanged before & after)
LIVE_BROKER_TRANSMISSION      = "BLOCKED"    (via /api/health, unchanged before & after)
Macro execution side effects  = NONE
```

- `test_macro_scorecard_has_no_execution_side_effect` — safety flags identical
  before/after hitting every new endpoint.
- `test_scorecard_module_imports_no_execution_module` — `api.macro_scorecard`
  binds no `execution_pipeline` / `broker_adapter` / `risk_gateway` /
  `reconciliation` module.
- Strategy contract SHA-256 `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` — **unchanged**.
- Historical baseline N=82 / dataset isolation — untouched (no test modified,
  full suite green).
- No macro endpoint places/modifies/cancels orders, transmits to a broker, or
  enables automation. All GET.

---

## 8. Lookahead verification

The scorecard flows entirely through
`EconomicDataRegistry.get_releases_as_of(as_of=...)`, which excludes any
release with `release_timestamp > as_of` (string-ISO comparison at the registry
boundary).

- `test_lookahead_future_releases_excluded` — `get_scorecard("USD", as_of=2026-08-10)`
  sees fewer releases than `as_of=2026-09-15` (`0 < n_early < n_late`).
- `test_lookahead_release_at_exact_as_of_is_included` — a release whose
  timestamp equals `as_of` **is** included; the same release 1 second earlier
  is **excluded**.
- `test_history_empty_state_is_honest_no_fabrication` — history is `NO_HISTORY`
  with no points until a real snapshot is recorded; then exactly that one
  point appears, carrying its payload SHA-256 fingerprint.
- `test_history_is_ordered_ascending_for_charting` — points are returned oldest
  → newest; no interpolation or synthetic points are added.

---

## 9. Test results

```
pytest tests/ -p no:randomly

1079 passed
2 skipped
0 failed
~68 s
```

New: `tests/test_phase64_macro_scorecard.py` — **20 tests** (composite
determinism, 6-category structure, evidence-backed rows, Technical/Sentiment
INSUFFICIENT, no-data currency, FX-pair both-legs rule, family-specific
surprise, heatmap impact divergence, 2× lookahead, heatmap country isolation,
heatmap missing-country, history empty + round-trip + ordering, provenance ×7,
API endpoints, API 404/422, response shape, no execution side effect, no
execution import). An autouse fixture restores the canonical
`EconomicDataRegistry` (another suite mutates the class-level singleton and
never restores it) — order-independent.

---

## 10. Frontend QA

**Full route regression** (headless Chrome / CDP, production build):
19 routes × (1280×720 / 1440×900 / 1920×1080) = 66 loads →
**0 console errors, 0 uncaught exceptions, 0 horizontal overflow**; command
palette + keyboard shortcuts working.

**Macro workflow** (1920×1080 / 1600×900 / 1280×720):

| Step | Result |
| :-- | :-- |
| Navigate `/research/macro` (Scorecard default tab) | ✅ gauge renders, category cards render |
| DEMO / SEEDED DATA label present | ✅ all resolutions |
| Technical / Sentiment show `INSUFFICIENT_EVIDENCE` | ✅ |
| Switch instrument USD → EUR → USDJPY | ✅ 0 errors, content updates |
| Economic Heatmap tab | ✅ 17 US indicator rows, Ccy-impact + Equity-impact columns |
| Select AUD (no data) | ✅ `INSUFFICIENT_EVIDENCE` |
| Horizontal overflow | ✅ 0 at every resolution / tab |
| Console errors | ✅ 0 |

`tsc -b` clean. `npm run build` clean (no chunk-size warning; macro chunk
33 kB / 8 kB gzip, lazy).

---

## 11. Performance

- New endpoints are **cache-free composites over the in-memory seed registry**
  (no per-request DB read except the best-effort snapshot write, hourly-deduped).
  In-process warm latency: `/api/macro/scorecard/XAUUSD` ~15–25 ms,
  `/api/macro/heatmap/USD` ~10 ms, `/api/macro/scorecard/USD/history` ~2 ms
  (SQLite) — all well under the Phase-63 budgets.
- Frontend: one `Promise.allSettled` batch per instrument (scorecard + history),
  no N+1, no per-category fetch. Phase 62 pooling / caches / code-split / warm-up
  all preserved (no change to `database.py`, `api/main.py`, `vite.config.ts`,
  `App.tsx`).
- Full suite duration unchanged (~68 s).

---

## 12. Git

```
commit:        <filled on commit>
working tree:  CLEAN
files:         6 modified (api/ai_context.py, api/routers/macro.py, api/schemas.py,
               frontend/src/{api/macro.ts, pages/MacroIntelligencePage.tsx, types/macro.ts})
               6 added (api/macro_scorecard.py, frontend/src/components/macro/{Gauge,MacroScorecard,MacroHeatmap}.tsx,
               frontend/src/lib/useMacroScorecard.ts, tests/test_phase64_macro_scorecard.py)
               + this report
no execution / broker / risk / reconciliation file touched
```

---

## 13. Remaining gaps

| Gap | Type | Detail |
| :-- | :-- | :-- |
| No live macro data | **data-provider gap** | Everything is `seed_demo`. Connect a real economic-calendar feed behind `MacroDataProvider` (env `MACRO_DATA_PROVIDER`) → `provider_is_live: true`; no app change needed. |
| Technical category | **data-provider gap** | Needs a macro-technical feed (chart-trend + seasonality). Per-instrument chart / MTF bias already lives on the Trading Workspace; wiring it into the macro layer is a deliberate future decision, not a fabrication. |
| Retail / Crowd Sentiment category | **data-provider gap** | Needs a retail-positioning feed (broker sentiment / AAII). COT (institutional) positioning is already shown. |
| EUR / GBP / JPY thin coverage | **data-provider gap** | Only GDP / CPI / rate seeded → their COT and Jobs categories are `INSUFFICIENT_EVIDENCE`. |
| CAD / AUD / NZD / CHF / CNY | **data-provider gap** | 0 seeded releases → `INSUFFICIENT_EVIDENCE` everywhere. |
| Score-over-time chart is sparse | **time gap (self-healing)** | The snapshot store was empty; it now records one point per instrument per hour on view. The chart fills in as the app is used — by design, never back-filled. |
| "Top Setups" full ranking grid | **UI gap** | The ranked data is served by `/api/macro/scorecard`; a dense multi-instrument grid view (screenshot 30-55) was not built this phase. |
| COT report / history, Retail Sentiment history, Geo-risk tracker, weekly calendar grid | **future enhancement** | Distinct EdgeFinder pages; out of scope for this phase. |

---

## STOP

Macro scorecard foundation built on the real engines. No fabricated data — every
value is either an evidence-backed engine output or an explicit
`INSUFFICIENT_EVIDENCE` with a named `next_dependency`. Safety invariants
unchanged; macro stays read-only context. No execution capability added.
