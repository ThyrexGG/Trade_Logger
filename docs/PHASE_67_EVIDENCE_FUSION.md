# Phase 67 — Unified Evidence Fusion & Asset Intelligence

*Architecture reference for the canonical, timestamp-correct, evidence-backed
asset context object introduced in Phase 67.*

---

## 1. Purpose

Before Phase 67 the repo had several independent intelligence engines
(Asset Edge / Phase 55, Macro / Phase 56, Regime / Phase 57, Command Center /
Phase 58, Macro Scorecard / Phase 64, FRED / Phase 65, multi-provider evidence /
Phase 66). Each surface (Market Intelligence UI, Asset Deep Dive, AI context,
Command Center, Scanner) re-assembled them differently, with no single
timestamp-correct representation.

Phase 67 adds **one orchestration layer** that normalises the *existing* engine
output into a canonical `AssetIntelligenceSnapshot`. It computes **nothing new** —
no new scores, no new data sources, no composite magic number.

It is an **analytical / contextual** layer. It is **not** an execution system and
has no code path that could submit an order.

---

## 2. Files

| File | Role |
| :-- | :-- |
| `api/evidence_model.py` | Canonical data model — enums + dataclasses. Pure representation, no I/O. |
| `api/evidence_fusion.py` | The fusion engine. `get_asset_intelligence(asset, as_of, timeframe)` + `ai_snapshot()`. TTL snapshot cache. |
| `api/routers/intelligence.py` | `GET /api/intelligence/asset/{asset}` (read-only). |
| `api/schemas.py` | `AssetIntelligenceResponse` + `EvidenceCategoryModel` + `EvidenceItemModel`. |
| `api/ai_context.py` | `_asset_evidence_context()` — feeds the canonical snapshot to the AI assistant. |
| `frontend/src/types/intelligence.ts` | `AssetIntelligence` + sub-types. |
| `frontend/src/api/intelligence.ts` | `getAssetIntelligence(asset, {asOf, timeframe})`. |
| `frontend/src/lib/useAssetIntelligence.ts` | Race-safe hook, per-`(symbol, asOf)` cache, no polling for historical. |
| `frontend/src/components/intelligence/EvidenceFusionPanel.tsx` | The panel on the Asset Deep Dive page. |

---

## 3. Canonical evidence model

### 3.1 `EvidenceItem`

One atomic, source-attributed observation. Fields that a source cannot supply
are `None` — **never a fabricated number**.

```
asset  category  metric  state  value  unit  direction  strength  confidence
source  source_id  provenance
as_of  available_timestamp  release_timestamp  observation_timestamp  vintage_timestamp
note
```

### 3.2 States (`EvidenceState`) — deliberately distinct

| State | Meaning |
| :-- | :-- |
| `AVAILABLE` | Real evidence, current. |
| `INSUFFICIENT_EVIDENCE` | A source exists but there is not enough data yet. |
| `PROVIDER_UNAVAILABLE` | **No source at all** (or the configured provider is down). |
| `STALE` | Real evidence, but past its freshness window. |
| `CONFLICT` | Two sources disagree. |
| `NOT_APPLICABLE` | The category does not apply to this asset. |

`PROVIDER_UNAVAILABLE` is **never** collapsed into `INSUFFICIENT_EVIDENCE`, and
neither is ever collapsed into a neutral score. Missing evidence stays
distinguishable from neutral evidence.

### 3.3 `CategoryEvidence`

Category-level roll-up. `score` / `direction` are the category's **own** (from its
authoritative engine) — they are **not** blended with other categories.

### 3.4 `AssetIntelligenceSnapshot`

```
asset  as_of  generated_at  mode(LIVE|HISTORICAL)  timeframe
categories[]           # CategoryEvidence, fixed order
cross_category         # CrossCategoryAssessment — agreement / conflict, explicit
coverage               # CoverageSummary — computed only from real category states
conflicts[]            # cross-category + within-category + macro-source conflicts
data_gaps[]            # missing categories + future-evidence exclusions
provenance[]           # traceable chain: category -> metric -> source_id -> source -> timestamps
provider_health        # macro provider registry state (Phase 66)
model_version  disclaimer  safety_barrier
```

There is **no** top-level `overall_score` / `composite_score`. A consumer that
wants a single number must justify its own weighting; the snapshot provides an
evidence matrix instead.

---

## 4. Categories and their real sources

Only categories with a real source in the repo are ever populated. The fixed
order is `TECHNICAL, SMC, MACRO, COT, REGIME, SEASONALITY, SENTIMENT`.

| Category | Source engine (reused, not reimplemented) | Notes |
| :-- | :-- | :-- |
| `TECHNICAL` | `AssetEdgeIntelligenceEngine` → "Technical Structure" factor | live only |
| `SMC` | same → "Smart Money & Liquidity" factor | live only |
| `SEASONALITY` | same → "Seasonality Tendencies" factor | live only |
| `MACRO` | `api.macro_scorecard.get_scorecard(asset, as_of)` for the composite + state; evidence items pulled straight from `EconomicDataRegistry.get_releases_as_of` for full provenance | **as-of correct** |
| `COT` | `EconomicDataRegistry` `COT_NET_POSITIONING` releases (Phase 66 CFTC) + `cot_provider_key()` for the empty-state reason | **as-of correct** |
| `REGIME` | `CrossAssetRegimeEngine.evaluate_regime()` | live only — see §6 |
| `SENTIMENT` | `api.providers.sentiment_provider` — no provider configured in the repo → `PROVIDER_UNAVAILABLE` | honest gap |

> The Phase-55 factor engines (`TECHNICAL` / `SMC` / `SEASONALITY`) currently use
> deterministic model priors keyed by symbol rather than live candle analysis for
> most instruments. The fusion layer faithfully reports their self-declared
> provenance (`derived`) and does not "upgrade" it. Replacing those priors with
> real market-structure analysis is a separate future item (§9).

---

## 5. Timestamp discipline

Two independent layers:

1. **Engine level** — every underlying call is made with the requested `as_of`.
   `EconomicDataRegistry.get_releases_as_of` already excludes
   `release_timestamp > as_of`.
2. **Fusion level (defence in depth)** — `_enforce_timestamps()` re-checks every
   emitted `EvidenceItem`. An item whose `available_timestamp` /
   `release_timestamp` is **strictly after** the ceiling is dropped and recorded
   in `data_gaps` as `FUTURE_EVIDENCE_EXCLUDED`. An item **exactly at** the
   ceiling is kept (`<=`).
   - LIVE ceiling = wall-clock now at enforcement time (sub-engines legitimately
     stamp evidence a few ms after the snapshot instant was frozen).
   - HISTORICAL ceiling = the requested `as_of`, exactly. An item with **no**
     knowable timestamp is also dropped in historical mode (we cannot prove it
     was available).

Regression tests: `tests/test_phase67_timestamp.py`
- future derived item excluded / exact-at-ceiling included
- future macro release excluded from an earlier snapshot
- future COT release excluded
- historical reconstruction: `snapshot(T1) != snapshot(T2)` when releases changed
- revised observation carries its `vintage_timestamp`
- historical mode excludes the live-only categories with a stated reason

---

## 6. Historical / as-of mode

`get_asset_intelligence(asset, as_of=<past instant>)` returns a snapshot
reproducible from information available by that instant only.

Only `MACRO` and `COT` are populated in historical mode — both flow through the
timestamp-disciplined registry. `TECHNICAL` / `SMC` / `REGIME` / `SEASONALITY`
are returned as `INSUFFICIENT_EVIDENCE` with an explicit `reason`
("no timestamp-correct historical reconstruction available … its factor engine is
live-only") rather than silently returning current values.

`CrossAssetRegimeEngine` reads `market_data` live-only (no as-of candle store),
so regime is deliberately **not** reconstructed historically — see §9.

---

## 7. Cross-category conflict

`_cross_category()` classifies the populated, directional categories:

| Result | Rule |
| :-- | :-- |
| `AGREEMENT` | every directional category agrees |
| `MIXED` | majority ≥ 75 % one way |
| `CONFLICT` | genuine split (< 75 % majority) |
| `INSUFFICIENT_EVIDENCE` | fewer than two directional categories |

A `CONFLICT` names `supporting_categories` and `opposing_categories`. It is
**represented, never averaged away** — the point is to make uncertainty visible.

---

## 8. Caching (Phase-62 idiom, no new system)

Module-level TTL snapshot cache in `evidence_fusion.py`, same pattern as
`CrossAssetRegimeEngine._REGIME_CACHE` / `system_health_cache`.

| Key namespace | TTL | Rationale |
| :-- | :-- | :-- |
| `live::{asset}::{tf}` | 4 s | matches the underlying engine caches |
| `hist::{asset}::{tf}::{as_of.isoformat()}` | process lifetime | historical results are deterministic and immutable |

A historical key is **never** served from a live entry and vice-versa — distinct
namespaces. `invalidate()` clears everything (test hook + provider-refresh hook).

**Measured** (TestClient, warm process):

| Endpoint | cold | warm |
| :-- | --: | --: |
| `GET /api/intelligence/asset/XAUUSD` | ~2.5 s¹ | ~6 ms |
| `GET /api/intelligence/asset/XAUUSD?as_of=…` | ~8 ms² | ~6 ms |
| `GET /api/intelligence/asset-profile/XAUUSD` (existing) | — | ~5 ms |
| `GET /api/macro/scorecard/USD` (existing, unchanged) | — | ~446 ms |
| `GET /api/command-center/overview` (existing) | — | ~35 ms |

¹ one-off per-process cost of first-time init of the Edge / Regime / Macro
engines — the same cost any intelligence page pays. `api/main.py` `_warm_up()`
now primes `…/asset/XAUUSD` at startup so the first real navigation is warm.
² warm because the live call already initialised the shared registry.

The macro-scorecard ~446 ms is **pre-existing Phase-56 architecture** (per-country
factor grouping + surprise evaluation over the registry) and was **not** rewritten
to chase a benchmark, per the phase brief. The fusion layer reuses its cached
result rather than adding a second pass.

---

## 9. Known limitations / future provider extension points

| Gap | Honest current behaviour | What would close it |
| :-- | :-- | :-- |
| `TECHNICAL` / `SMC` / `SEASONALITY` use symbol-keyed model priors | reported as `provenance: derived`, populated live only | wire the Phase-55 factor engines to real MTF candle analysis; then they become as-of-reconstructable |
| `REGIME` not reconstructable historically | `INSUFFICIENT_EVIDENCE` + reason in historical mode | an as-of cross-asset price store for regime replay |
| `SENTIMENT` has no provider | `PROVIDER_UNAVAILABLE` | register a broker / crowd-positioning provider under the Phase-66 registry (`Capability.RETAIL_SENTIMENT`) |
| No defensible overall composite | evidence matrix + cross-category assessment only | a scientifically justified, documented weighting framework |
| Coverage of non-USD economies | `MACRO` / `COT` resolve to `INSUFFICIENT_EVIDENCE` where the registry has no releases | a real economic-calendar + COT provider covering EUR/GBP/JPY/AUD/… |

New providers plug into the existing Phase-66 `MacroProviderRegistry` — the
fusion layer never learns a vendor name, only a `Capability`.

---

## 10. Safety

- No import of / path to `execution_pipeline`, `broker_adapter`, `risk_gateway`,
  `reconciliation`, `order_execution` — enforced by `tests/test_phase67_safety.py`
  and `tests/test_phase67_ai.py` (bound-module scan + source scan).
- `snapshot.safety_barrier = {live_automation_enabled: False, live_broker_transmission: "BLOCKED"}`.
- `disclaimer` states the snapshot is "never an execution signal".
- The AI `SYSTEM_INSTRUCTION` is extended: a category marked
  `INSUFFICIENT_EVIDENCE` / `PROVIDER_UNAVAILABLE` has no reading and must not be
  filled in; a `CONFLICT` must be reported, not resolved.
- No secret is ever included in the response (`provider_health` carries state /
  coverage / error-kind only). Verified by `test_no_secret_in_response`.
- Frozen Strategy Contract SHA-256 unchanged:
  `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`.
- No execution / broker / risk / reconciliation file was modified.

---

## 11. Tests

`tests/test_phase67_evidence_model.py` · `tests/test_phase67_timestamp.py` ·
`tests/test_phase67_fusion.py` · `tests/test_phase67_api.py` ·
`tests/test_phase67_ai.py` · `tests/test_phase67_safety.py`
