# STAGE 11 — Streamlit Legacy UI Retirement Evaluation

**Roadmap reference:** `docs/REACT_MIGRATION_AUDIT.md` §6 — "[ONLY THEN: Streamlit Legacy UI Retirement Evaluation]" (the step after STAGE 10)
**Baseline commit:** `397ed07` — `docs(migration): Stage 10 final integration & performance gate audit`
**Date:** 2026-09-02
**Type:** architectural / dependency evaluation — **no source deletion**

---

## 1. Executive Summary

**Recommendation: KEEP STREAMLIT (Option C).** Retirement risk today is **MEDIUM–HIGH**.

The React SPA has replaced ~10 of Streamlit's monitoring/analysis surfaces with
verified parity (Stage 10 PASS). However, `app.py` still uniquely provides
**seven distinct operational and research workflows with no React or FastAPI
equivalent**, including the only interactive order-entry path (Quick Terminal,
paper/shadow mode) and the local-LLM AI Market Context. In addition:

- The `streamlit` **pip package is a hard runtime import dependency of the
  FastAPI adapter** (via `trading_workspace_cockpit`, `user_preferences`,
  `market_intelligence_command_center`). It cannot be removed from
  `requirements.txt` without refactoring those three modules.
- The **only documented deployment** (`deployment_guide.md`) is
  `streamlit run app.py`; there is no React/FastAPI deployment configuration.
- The migration roadmap's invariant #5 ("Streamlit Coexistence") keeps `app.py`
  operational as fallback / golden reference; this eval is explicitly scoped to
  *evaluate*, not delete.

Streamlit **is not fully superseded**. The correct posture is coexistence:
React as the read-only monitoring/analysis SPA, Streamlit as the power-user
console for the non-migrated workflows, until the user makes an explicit product
decision about the remaining surfaces.

---

## 2. Streamlit Inventory

`app.py` (4,432 lines, ~335 Streamlit widget calls, Streamlit 1.62.0) exposes a
**4-zone × 14-subview** architecture:

| Zone | Subview | Backing modules |
| :-- | :-- | :-- |
| **TRADING WORKSPACE** | CHARTS & WORKSPACE | `trading_workspace_cockpit`, `tradingview_widget`, `asset_edge_scorecard`, `risk_gateway` |
| | MARKET SCANNER & REGIME | `market_intelligence_scanner`, `cross_asset_regime_engine`, `market_intelligence_ui` |
| | QUICK TERMINAL | `execution_pipeline.submit_order` (**manual paper/shadow order entry**), `broker_adapter` |
| | AI MARKET CONTEXT | `ai_analysis` + **Ollama local LLM** (`ollama>=0.1.0`) |
| | PRICE ALERTS | `alerts` (price-alert CRUD + rules engine + background worker) |
| **RESEARCH & STRATEGY LAB** | RESEARCH LAB OVERVIEW | `research_engine` (3-layer train/val/holdout), `true_mtf_engine`, `usdjpy_research`, `usdjpy_edge_discovery`, `usdjpy_continuation_research` |
| | XAUUSD ADVERSARIAL AUDIT | `xauusd_overnight_experiment`, adversarial stress harnesses |
| | STRATEGY SANDBOX | `backtester` + `research_engine` scorecard classifier |
| **FORWARD EVIDENCE & GOVERNANCE** | FORWARD EVIDENCE CENTER | `forward_evidence_cockpit` (7 tabs: Overview, Statistics, Milestones, Stability/Alpha-Decay, Observation Pipeline, Forensics & Reconciliation, Governance Ledger) |
| | ADVERSARIAL STRESS AUDIT | XAUUSD adversarial audit |
| **OPERATIONS, JOURNAL & AUDIT** | DAILY COMMAND CENTER | `xauusd_daily_command_center` (preflight, session context, `DailyResearchJournal` notes) |
| | ANALYTICS & OVERVIEW | `analytics`, `research_analytics` (performance analytics) |
| | TRADE JOURNAL | `database.get_closed_trades` + `update_trade_journal` (**editable** setup_tag/notes/rating) |
| | SYSTEM HEALTH & PAPER OPS | `system_health.evaluate_system_health`, paper ops, `capital_sync`/`mt5_sync` status |

Plus a persistent 4-zone nav, telemetry ribbon, command palette, keyboard
shortcuts and workspace-layout switcher (`workspace_layout_manager`).

---

## 3. React Parity Matrix

| Streamlit capability | React replacement | Route | Backend | Status |
| :-- | :-- | :-- | :-- | :-- |
| Watchlist (10 fields, search, class filter) | Watchlist | `/workspace`, `/workspace/market` | `GET /api/watchlist` | **FULLY_REPLACED** |
| Market Snapshot / MTF bias hierarchy / SMC levels | Market Snapshot | `/workspace/market` | `GET /api/market/snapshot/{sym}` | **FULLY_REPLACED** (TradingView iframe intentionally not migrated) |
| Pre-trade risk sizing / lot calc / worst-case risk / rewards | Risk Gateway | `/workspace/risk` | `POST /api/risk/preview` | **FULLY_REPLACED** (+ currency-aware FX fix `d23a54f`) |
| Open positions + MAE/MFE excursion | Positions | `/workspace/positions` | `GET /api/positions` | **FULLY_REPLACED** |
| Market Scanner & Regime / Opportunity Map / Heatmap / Asset drill-down | Market Intelligence + Asset Intelligence | `/research/intelligence`, `/research/intelligence/asset/:symbol` | `GET /api/intelligence/{summary,opportunity-map,heatmap,asset-profile}` | **FULLY_REPLACED** (correlation matrix / regime-transition ledger omitted — API does not expose) |
| Forward Evidence — core metrics / uncertainty / holdout / milestones / decision / dataset | Forward Evidence + Statistics + Governance | `/evidence`, `/evidence/{forward,statistics,governance}` | `GET /api/forward-evidence/state` | **PARTIALLY_REPLACED** — React = 4 pages vs Streamlit 7-tab cockpit; Observation Pipeline, Forensics & Reconciliation, and the milestone-snapshot ledger are not in React (API gap, Stage 9) |
| Strategy contract / methodology / registered strategies | Strategy Lab | `/research/strategy` | `GET /api/research/strategy` | **FULLY_REPLACED** (read-only config surface) |
| Standard backtest + walk-forward + Monte-Carlo | Backtest Workspace | `/research/backtest` | `POST /api/research/backtest` | **PARTIALLY_REPLACED** — `backtester.run_backtest`/`run_walk_forward` covered; the 3-layer `research_engine` workflow, scorecard classifier, multiple-testing tracker and per-window WFO detail are not |
| Trade Journal (view) | Trade Journal | `/operations/journal` | `GET /api/operations/journal` | **PARTIALLY_REPLACED** — React is read-only; Streamlit `update_trade_journal` (edit setup_tag/notes/rating) has no API |
| Execution audit trail | Operational Audit | `/operations/audit` | `GET /api/operations/audit` | **FULLY_REPLACED** (`execution_orders`) |
| System Health & safety gate | System Health | `/operations/system` | `GET /api/health`, `GET /api/operations/system` | **FULLY_REPLACED** |
| Operational overview | Operations | `/operations` | fan-out | **FULLY_REPLACED** |
| 4-zone nav / telemetry ribbon / command palette / hotkeys / layout switcher | App shell | all routes | — | **FULLY_REPLACED** |
| Quick Terminal — manual paper/shadow **order submission** | — | — | — | **NOT_REPLACED** — React is read-only by design |
| AI Market Context (Ollama local LLM analysis) | — | — | — | **NOT_REPLACED** |
| Price Alerts (create / edit / delete / rules) | — | — | — | **NOT_REPLACED** |
| Analytics & Overview (performance analytics) | — | — | — | **NOT_REPLACED** |
| Daily Command Center (preflight, session context, research journal notes) | — | — | — | **NOT_REPLACED** |
| Research Lab (True MTF lab, USDJPY empirical labs, edge discovery) | — | — | — | **NOT_REPLACED** |
| Adversarial Stress Audit (XAUUSD overnight experiment) | — | — | — | **NOT_REPLACED** |

**Summary:** 11 surfaces FULLY_REPLACED · 3 PARTIALLY_REPLACED · 7 NOT_REPLACED.

---

## 4. Streamlit-Only Capabilities

| Capability | Location | Used by | React repl.? | Backend repl.? | Removable? | Risk if removed | Recommendation |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| Manual paper/shadow order entry ("SUBMIT BUY/SELL ORDER") | `app.py:4120–4180` → `execution_pipeline.submit_order` | Trader (manual forward-evidence generation), also `server.py` legacy engine | No (SPA is read-only by design) | `execution_pipeline` is intact and callable; no HTTP surface | No — no replacement | Loss of the only interactive way to record a paper/shadow trade from a UI | **KEEP** (or explicit product decision to drop manual entry) |
| AI Market Context | `ai_analysis.py` + Ollama | Trader (pre-trade narrative) | No | No | No | Loss of the local-LLM analysis workflow | **KEEP** / this is the future "AI Assistant" stage's territory |
| Price Alerts CRUD + rules engine | `alerts.py` + Streamlit UI | Trader; background `price_alert_worker` daemon runs independently | No | No `/api/alerts` | No | Cannot create/manage alerts from a UI (daemon still fires existing ones) | **MIGRATE FIRST** if retiring — small, well-bounded (`alerts.py` is a clean module) |
| Analytics & Overview | `analytics.py`, `research_analytics.py` | Trader (equity curve, R-distribution, session stats) | Partial (backtest metrics only) | No | No | Loss of the historical-performance analytics view | **KEEP** / candidate for a future adapter |
| Daily Command Center | `xauusd_daily_command_center.py` | Trader (daily preflight, `DailyResearchJournal.add_note`) | No | No | No | Loss of the daily-preflight workflow and research-note capture | **KEEP** |
| Research Lab (True MTF, USDJPY labs, edge discovery, 3-layer research) | `true_mtf_engine.py`, `usdjpy_*.py`, `research_engine.py` | Researcher | No (React Backtest ≠ research workflow) | Partial (`backtester` only) | No | Loss of the primary strategy-research environment | **KEEP** |
| Adversarial Stress Audit | `xauusd_overnight_experiment.py` etc. | Researcher | No | No | No | Loss of the adversarial validation workflow | **KEEP** |
| Editable trade journal (setup_tag / notes / rating) | `database.update_trade_journal` via `app.py` | Trader | No (React journal read-only) | No write endpoint | No | Cannot annotate trades | **MIGRATE FIRST** if retiring — needs a `PATCH /api/operations/journal/{trade_id}` write endpoint |
| Full 7-tab Forward Evidence cockpit | `forward_evidence_cockpit.py` | Researcher / governance | Partial (4 React pages) | Partial (`/api/forward-evidence/state`) | No | Loss of Observation Pipeline, Forensics & Reconciliation, milestone-snapshot ledger views | **KEEP** for those tabs |

---

## 5. Backend Dependencies

### 5.1 `streamlit` package is a HARD dependency of the FastAPI adapter

Module-level `import streamlit as st` in three modules that FastAPI routers import:

| Module | Imported by router | Import type |
| :-- | :-- | :-- |
| `trading_workspace_cockpit.py:20` | `api/routers/market.py`, `api/routers/watchlist.py` | **hard, module-level** |
| `user_preferences.py:19` | `api/routers/preferences.py` | **hard, module-level** |
| `market_intelligence_command_center.py:42` | `api/routers/intelligence.py` | **hard, module-level** |

`database.py`, `alerts.py`, `capital_sync.py`, `application_performance_profiler.py`
use a **conditional** `try: import streamlit` and do not require it.
The authoritative engines (`risk_gateway`, `market_data`, `backtester`,
`xauusd_forward_statistical_monitoring`, `strategies/*`) do **not** touch Streamlit.

**Consequence:** the Streamlit *process* can stop, but `streamlit>=1.30.0` must
stay in `requirements.txt` (installed 1.62.0) or the React SPA's backend fails to
import. Removing the package requires making those three imports conditional.

### 5.2 Data ingestion is independent of Streamlit

`closed_trades` / `open_positions` are populated by the standalone sync daemons
`mt5_sync.py`, `auto_sync.py`, `capital_sync.py` (each has `if __name__ == "__main__"`)
and by the reconciliation worker — not by Streamlit. `execution_orders` rows carry
`source` values (`COCKPIT_*`, `exec_rec_*`, `test_*`, `MANUAL_UI`); only `MANUAL_UI`
originates from `app.py`. The forward-evidence statistical pipeline
(`xauusd_forward_statistical_monitoring`) reads these tables regardless of writer.

### 5.3 Streamlit → internal function, with no React → FastAPI path

`app.py` calls these directly with no adapter equivalent: `execution_pipeline.submit_order`,
`ai_analysis.*` (+ Ollama), `alerts.*` (CRUD), `analytics.*` / `research_analytics.*`,
`xauusd_daily_command_center.*`, `research_engine.*` (full workflow),
`database.update_trade_journal`, `forward_evidence_cockpit` Observation-Pipeline /
Forensics tabs.

---

## 6. Safety Analysis

**Retirement does not affect any safety mechanism.** All fail-closed logic lives in
the backend and is independent of the UI:

- `LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = "BLOCKED"` — enforced
  in `execution_pipeline` / `broker_adapter` / `system_health`, not in `app.py`.
- `/api/health` and `/api/operations/system` confirm `automation_enabled=false`,
  `live_broker_transmission=BLOCKED` — unchanged.
- Targeted regression: `test_phase62_safety.py`, `test_execution_safety.py`,
  `test_api_parity_stage2/3.py`, `test_forex_position_sizing.py` — **55 passed**.

**However:** `app.py`'s Quick Terminal is UI that *reaches* `execution_pipeline`.
Retiring `app.py` removes that reach in PAPER/SHADOW mode. It does **not** remove
`execution_pipeline` itself (still used by `server.py`, audit harnesses, and the
reconciliation path). No execution-related backend functionality should be
touched by a retirement.

**Execution / mutation audit of `app.py`:** `submit_order` (Quick Terminal, `source="MANUAL_UI"`,
`mode` defaults to `PAPER`), `broker_adapter.get_broker_adapter` (health/status reads +
paper fills), `database.update_trade_journal` / `update_setup_tag` (journal annotations),
`database.set_setting` (`SYSTEM_STATE`, kill switch — operator controls). The BUY/SELL
buttons are gated by an "AI Validation Lock" and the fail-closed barrier. This is
calculation-plus-**paper-execution-capable**, not dead code.

---

## 7. Deployment Analysis

| Artifact | Streamlit dependency |
| :-- | :-- |
| `deployment_guide.md` | Start command **`streamlit run app.py --server.port $PORT`** (Streamlit Cloud / Render). This is the **only documented deployment**. |
| `.streamlit/config.toml` | Streamlit theme + headless/server config |
| `instruction.md` | `streamlit run app.py` (local dev instruction) |
| `docs/04_Component_Breakdown.md` | Describes `app.py` as "the main entry point" |
| `docs/REACT_MIGRATION_AUDIT.md` §0 #5, §3A.4, §7 checklist | "Streamlit Coexistence" invariant; "operational on port 8501 as golden reference"; `[ ] Streamlit fallback operational on port 8501` |
| `frontend/README.md:47` | "Streamlit … remains the golden reference" |
| `start_flutter.bat`, `start_silent.vbs` | **No Streamlit** — launch the legacy `server.py` (Flutter engine) on :8000 |
| CI / Docker / Procfile / docker-compose | **None exist** |
| `.claude/settings.local.json` | dev-only `curl :8501/_stcore/health` allow-list entry |

**There is no deployment configuration for the React + FastAPI stack.** Retiring
Streamlit leaves the project with no documented deployed UI until a
React-static + FastAPI deployment is defined. `frontend/` builds to `dist/`
(431.81 kB JS / 119.20 kB gzip) and the adapter is `api.main:app`, but nothing
wires them for production.

---

## 8. Test Results

| Check | Result |
| :-- | :-- |
| `npx tsc -b` | ✅ clean |
| `npm run build` | ✅ clean, 142 modules, 431.81 kB JS / 119.20 kB gzip, no new deps |
| Targeted backend (`test_phase62_safety`, `test_api_parity_stage2/3`, `test_execution_safety`, `test_forex_position_sizing`) | ✅ **55 passed** |
| React smoke (`/`, `/workspace/positions`, `/operations/audit`, `/evidence`, `/research/strategy`) | ✅ all 200 |
| Streamlit `:8501/_stcore/health` | ✅ `ok` |
| Adapter `/api/health` safety flags | ✅ `automation_enabled=False`, `live_broker_transmission=BLOCKED` |

Known pre-existing / unrelated failures (`test_backtester.py::test_lot_rounding`,
`test_ws.py::test_websocket_stream` — gitignored scratch files) — not re-run, not
in scope, per the Stage 10 audit.

**No source files were changed by this evaluation.**

---

## 9. Retirement Risk Assessment

**Overall: MEDIUM–HIGH.**

| Dimension | Risk | Reason |
| :-- | :-- | :-- |
| Feature parity | **HIGH** | 7 workflows have no React/FastAPI equivalent; 3 more are partial |
| Backend coupling | **MEDIUM** | `streamlit` is a hard import dep of the adapter via 3 modules (package must stay; process can stop) |
| Deployment | **HIGH** | Only documented deployment is `streamlit run app.py`; no React/FastAPI deploy config exists |
| Safety | **LOW** | All fail-closed logic is backend and UI-independent; verified unchanged |
| Data pipeline | **LOW** | Ingestion (`mt5_sync`, reconciliation) and the forward-evidence pipeline are Streamlit-independent |
| Reversibility | **LOW→MEDIUM** | Stopping the process is fully reversible; deleting `app.py` + 15 UI modules is a large irreversible change |

---

## 10. Recommendation

### KEEP STREAMLIT

Streamlit is **partially superseded, not fully superseded**. React covers the
read-only monitoring/analysis surfaces with verified parity; Streamlit remains the
only home for manual paper/shadow order entry, the local-LLM AI context, price
alerts, performance analytics, the daily command center, the strategy research lab,
adversarial audits, editable journal annotations, and three Forward-Evidence tabs.
The `streamlit` package is also a hard backend dependency and the only documented
deployment path.

This is a **coexistence** outcome, not a defect: React = read-only terminal for
monitoring, intelligence, evidence and risk analysis; Streamlit = power-user
console for research, alerts, analytics and paper execution.

---

## 11. Proposed Next Step

The genuinely next-smallest step is a **product decision by the owner**, not an
engineering task:

> **Decision required:** Are the seven non-migrated Streamlit workflows (manual
> paper execution, AI Market Context, Price Alerts, Analytics, Daily Command
> Center, Research Lab, Adversarial Audits) *in scope* for the React SPA, or is
> Streamlit the permanent home for them?

- **If they stay in Streamlit permanently** → mark this evaluation `KEEP` and
  update the roadmap invariant #5 from "until parity verified" to "permanent
  coexistence"; add a short `docs/` note delineating "use React for X, Streamlit
  for Y". No code change.
- **If the SPA should eventually own them** → the smallest concrete migration
  units, in ascending risk:
  1. `PATCH /api/operations/journal/{trade_id}` + React journal edit (setup_tag /
     notes / rating) — smallest, no new engine.
  2. `GET/POST/DELETE /api/alerts` + React Price Alerts page — `alerts.py` is a
     clean, bounded module.
  3. `GET /api/analytics/*` + React Analytics page — read-only pass-through of
     `analytics.py` / `research_analytics.py`.
  4. (larger, separate stages) Daily Command Center, Research Lab, the AI
     Assistant stage, and — only with an explicit execution-scope authorization —
     a paper-execution surface.

Either way: **do not delete `app.py` or any Streamlit module in this stage.**
The roadmap does not authorize deletion here, and the evidence does not support
immediate retirement.

---

## 12. Verdict

**Streamlit is retained.** No changes to source, dependencies, deployment,
execution logic or safety mechanisms. The evaluation is recorded; the retirement
decision is deferred to an explicit product-scope decision by the owner.
