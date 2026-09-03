# TradeLogger — Current State

*Source-of-truth snapshot for future prompts. Written during the stabilization
pass (after `534f574`). Pair with `CURRENT_ARCHITECTURE.md`.*

---

## What is TradeLogger right now?

A **read-only trading terminal, research lab and market/macro intelligence
console**. It records and reviews trades (paper/shadow), analyses historical
performance, runs backtests and adversarial research audits, tracks a frozen
XAUUSD strategy's forward statistical evidence, surfaces market regime / macro
context, and answers analytical questions about your own data via a read-only
Gemini assistant.

It **does not place, modify, cancel or transmit any order**, and has no code
path that could. Live automation is permanently disabled.

The modern product is the **React SPA + FastAPI adapter**. The **Streamlit app
(`app.py`, :8501)** is kept as the golden reference and still hosts a few
power-user workflows not yet migrated.

---

## Major functionality currently implemented

| Area | State |
| :-- | :-- |
| Unified Evidence Fusion (Phase 67) — `GET /api/intelligence/asset/{asset}`, one canonical timestamp-correct evidence object per asset; Asset Deep Dive `EvidenceFusionPanel`; AI `asset_evidence` context | **production-safe**, read-only. Orchestrates existing engines; `MACRO`+`COT` are as-of-correct, live-only categories honestly marked. See `docs/PHASE_67_EVIDENCE_FUSION.md`. |
| Trading Workspace — watchlist, market snapshot, MTF/SMC context | **production-safe**, live data |
| Risk Gateway — position sizing / pre-trade risk preview (currency-aware FX) | **production-safe**, calc only |
| Positions — open paper/shadow positions + excursion metrics | **production-safe**, live data |
| Daily Command Center — "what matters today" aggregate | **production-safe**, live data (warm p50 ~26 ms since Phase 62) |
| Price Alerts — CRUD; evaluation by the `auto_sync` daemon | **production-safe** |
| Analytics — filtered performance over the closed-trade journal | **production-safe**, byte-parity with canonical engine |
| AI Assistant — read-only analytical chat (Gemini) | **production-safe when `GEMINI_API_KEY` is set**; graceful "not configured" otherwise |
| Market Intelligence — cross-asset regime, breadth, opportunity map, economic heatmap | **production-safe**, live compute |
| Macro Intelligence — economic calendar, surprise, currency strength, asset macro context | **foundation only — DEMO / SEEDED DATA** |
| Strategy Lab + Backtesting + Edge Audit | **production-safe** (yfinance history) |
| Forward Evidence & Governance | **production-safe**; currently N=0 forward observations |
| Journal / Audit / System Health | **production-safe**; journal annotations editable |

---

## Intentionally read-only

Everything. Specifically: market data, macro intelligence, analytics, research,
evidence, command centre, the AI assistant, and all `/api/*` endpoints except
the handful of calc/CRUD-for-annotations ones listed in
`CURRENT_ARCHITECTURE.md §3`. No endpoint reaches `execution_pipeline`,
`broker_adapter` or `risk_gateway` for mutation.

## Intentionally disabled

- **Live trading / broker transmission** — `LIVE_AUTOMATION_ENABLED = False`,
  `LIVE_BROKER_TRANSMISSION = "BLOCKED"`. Permanent.
- **Manual order entry in React** — the Streamlit "Quick Terminal" is the only
  UI that can submit a paper/shadow order; it was deliberately not migrated.
- **AI execution** — the assistant explains but cannot act.

## Production-safe

The whole React SPA + `api.main:app`, backed by the authoritative engines.
Live data flows for market / positions / analytics / intelligence / research /
evidence. 1043 tests pass.

## Demo / seeded data (NOT real)

- **All macro intelligence** (`/api/macro/*`, `/research/macro`) — the default
  `SeedDemoProvider` serves synthetic 2026 economic values for USD/EUR/GBP/JPY
  only. Every response is tagged `provenance: "seed_demo"`,
  `provider_is_live: false`; the UI shows a permanent "DEMO / SEEDED DATA"
  banner; CHF/CAD/AUD/NZD return `INSUFFICIENT_EVIDENCE`. A real feed connects
  via `MACRO_DATA_PROVIDER` with one provider class, no other change.
- Forward-evidence sample size is genuinely N=0 (no forward trades yet) — that
  is real, not seeded.

## What remains incomplete

- **Macro "scorecard" layer** — composite integer bias, gauges, 6-category
  per-instrument scorecard, score-over-time sparkline, per-country heatmaps.
  **PARKED** (see `FUTURE_WORK.md`).
- **Real macro data provider** — not connected.
- **Streamlit-only workflows** — AI Market Context (Ollama), notification-rules
  engine, daily-command-center note/snapshot *writing*, some USDJPY/True-MTF
  research labs, adversarial audits.

**Done in Phase 62** (was here as incomplete): DB connection pooling,
`/api/operations/{audit,system}` caching, command-centre latency, frontend
code-splitting. See `PERFORMANCE_REPORT.md`. All warm API p50 ≤ 40 ms.

## What should NOT be changed

- The strategy contract SHA-256 (`xauusd_market_conditions.FROZEN_CONTRACT_HASH`) — byte-exact.
- The locked historical holdout baseline (N=82, E[R]=+0.637R, WR=58.6%, PF=2.52) — locked, unpooled.
- Dataset isolation (`IDs_hist ∩ IDs_paper = ∅`, `IDs_hist ∩ IDs_shadow = ∅`).
- `LIVE_AUTOMATION_ENABLED` / `LIVE_BROKER_TRANSMISSION`.
- `execution_pipeline.py`, `broker_adapter.py`, `risk_gateway.py` behaviour, the
  fail-closed safety barriers, the reconciliation worker.
- `app.py` (Streamlit) and `server.py` (legacy engine) — leave untouched.
- The macro seed/provenance/`INSUFFICIENT_EVIDENCE` behaviour — do not "fill in"
  demo data.
- Lookahead protection (`release_timestamp <= as_of`) anywhere — including the
  Phase-67 fusion layer's independent `_enforce_timestamps` guard.
- The Phase-67 evidence model's state distinctions — `PROVIDER_UNAVAILABLE` ≠
  `INSUFFICIENT_EVIDENCE` ≠ neutral; no blended composite; conflicts not averaged.

## Recommended next development area

1. ~~**Performance phase**~~ — **done (Phase 62).** DB pooling, endpoint caches,
   startup warm-up, frontend code-splitting. `PERFORMANCE_REPORT.md`.
2. **Macro real-provider + scorecard** — with the reference screenshots the
   user will supply. Still PARKED (`FUTURE_WORK.md`).
3. **Streamlit workflow migration** — notification-rules engine and
   daily-command-centre writes are the smallest remaining units.

Decide separately; this phase does not start any of them.
