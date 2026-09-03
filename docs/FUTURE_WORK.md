# TradeLogger — Future Work

*Maintained as the backlog. Nothing here is an active task — the next phase is
chosen separately from the stabilized current state.*

---

## CURRENTLY IMPLEMENTED

React SPA + FastAPI adapter covering: Command Center, Market Workspace, Risk
Gateway, Positions, Price Alerts, Analytics, AI Assistant, Market Intelligence,
Macro Intelligence (demo data), Strategy Lab, Backtesting, Edge Audit, Forward
Evidence & Governance, Journal / Audit / System Health. Read-only Gemini
assistant with an allowlisted context (incl. bounded macro snapshot).
1043 tests passing. Performance baseline measured (`docs/performance_baseline.json`).

---

## DONE

- **Performance phase (Phase 62)** — DB connection pooling, TTL caches on
  `/api/operations/{audit,system}` and command-centre sections, FastAPI startup
  warm-up, frontend route-level code splitting. All warm API p50 ≤ 40 ms; cold
  data path −85–99%. See `PERFORMANCE_REPORT.md` + `PHASE_62_REPORT.md`.

## NEXT (small, well-scoped, low risk)

- **Command-centre per-section timeout** (`TECHNICAL_DEBT.md` P3-2) — lower risk
  now that the I/O-heavy sections are cached, but still worth doing.
- **Combine the `/api/operations/audit` cold queries** (`TECHNICAL_DEBT.md` P3-4).
- **Import / lint tidy** with `ruff` across `api/` (P2-2).

## LATER (bigger, needs its own design + regression)

- **`database.py` split** into `db/` submodules (the pool now lives at the top
  of it; a `db/connection.py` is the natural first slice).
- **Co-located Postgres / read replica** — the pool removed the connect
  handshake but not the ~125 ms/query RTT to the managed instance. This is an
  infra decision, and the only structural fix left for DB-bound endpoints.
- **Migrate the remaining Streamlit workflows:** notification-rules engine
  (`alerts.get_alert_rules` / `save_alert_rules`), daily-command-centre note /
  snapshot *writing*, AI Market Context (Ollama), USDJPY / True-MTF research
  labs, adversarial audits. Each is an independent unit; see
  `STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md §11`.
- **Retire `server.py`** once nothing launches it; then evaluate retiring
  `app.py`.
- **True MAE/MFE from bar data** in `research_analytics` (`TECHNICAL_DEBT.md` P3-1).

## PARKED — Macro "EdgeFinder-style" scorecard layer

Explicitly parked (Stage 18 §18I). **Do not implement in an unrelated task.**
All of the following are additive on top of the Stage 18 foundation and require
the user's reference screenshots to specify:

1. **Real macro data provider** — a live economic-calendar feed behind the
   `MacroDataProvider` protocol (`api/macro_provider.py`). Server-side
   credentials, `provider_is_live = True`, events `provenance = "live"`.
2. **Composite integer bias score + gauge UI** per instrument (the seed engine
   already produces a float −100..100 score; needs bucketing + a gauge component).
3. **Per-instrument 6-category scorecard** (Technical Signal / Institutional
   Activity (COT) / Sentiment Bias / Eco Growth / Jobs Market / Inflation), each
   Bullish/Bearish/Neutral with a sub-score and "X vs. forecast" comparison rows.
   Data mostly exists in `macro_intelligence_engine` factor groups + the
   surprise engine; needs a `/api/macro/scorecard/{instrument}` shape + React.
4. **"Score over time" sparkline** — start writing
   `macro_intelligence_engine.MacroIntelligenceSnapshotStore` on a schedule, add
   a `/api/macro/.../history` endpoint, render a sparkline.
5. **Per-country economic heatmaps** (US / EU / UK / JP / CA / AU / NZ / CH) —
   `economic_heatmap.EconomicHeatmapEngine` exists (US-centric, 5 categories);
   needs a per-country parameter + dashboard wiring.
6. **Dedicated COT / Crowd-Sentiment panels** — `SENTIMENT_POSITIONING` factor
   group + `COT_NET_POSITIONING` seed exist; surface them as first-class sections.

**Constraints for whoever picks this up:** keep `seed_demo` / `provenance` /
`INSUFFICIENT_EVIDENCE` / read-only behaviour; never fabricate macro data;
contextual intelligence must never become an execution trigger.

## PARKED — not planned

- Any form of live / paper / shadow / automated execution in the React SPA.
- Broker transmission, order routing, position mutation endpoints.
- Enabling `LIVE_AUTOMATION_ENABLED`.
- Turning macro / technical / sentiment / regime signals into trade actions.
