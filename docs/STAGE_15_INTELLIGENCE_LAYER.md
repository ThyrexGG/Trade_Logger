# STAGE 15–17 — Intelligence Layer

**Baseline:** `536c3f1` (Stage 14). **Branch:** `main`.
**Commits:** `5397ba2` (15A) · `0c2b2fd` (15B) · `0f77d24` (15C).
Three independently gated checkpoints — Daily Command Center → Research Lab →
read-only Gemini AI Assistant.

Scope did **not** include: any execution (live / paper / shadow), broker order
submission, automation, execution-pipeline / risk-gateway / broker-adapter
changes, strategy mutation, Streamlit removal, the EdgeFinder-style macro
system, or unrelated bug fixes.

---

## 15A — Daily Command Center  (`5397ba2`)

### Audit
The Streamlit "DAILY COMMAND CENTER" is `xauusd_daily_command_center.DailyTradingCommandEngine`
— XAUUSD-only, heavy (live MTF state engine + ~15 news / calendar / reliability
auditors + network calendar providers), and coupled to the frozen XAUUSD
contract + forward-evidence pipeline. Migrating it verbatim was out of proportion
and out of scope (§34 defers the macro layer). The authoritative daily data is
already exposed piecemeal via migrated adapters (analytics, positions, alerts,
intelligence, forward-evidence, system health).

### Implementation
`GET /api/command-center/overview` — a server-side aggregator that re-shapes
slices of those already-authoritative sources into one payload. **No formula is
reimplemented.** Sections:

| Section | Source (reused, in-process) |
| :-- | :-- |
| `session` | pure UTC-hour computation (no network) |
| `safety` | `system_health.evaluate_system_health` + fail-closed flags |
| `daily_performance` / `account_summary` | `analytics.calculate_performance_metrics` (today slice + all-time) + `database.get_account_balances` |
| `positions` | `database.get_open_positions` (null-safe) |
| `alerts` | `database.get_all_price_alerts` |
| `market_context` | `UnifiedMarketIntelligenceAggregator.aggregate_market_state` |
| `research_state` | `Phase49MonitoringFacade.get_cached_forward_state_snapshot` |
| `research_notes` | `DailyResearchJournal.get_notes` (read-only) |
| `watchlist_highlights` | `TradingWorkspaceCockpit.get_watchlist_data` |

Sections run **concurrently** (`ThreadPoolExecutor`) → the overview is bounded by
the slowest source (~2.3 s cold / ~0.9 s warm), not their sum. A failing source
degrades only its section (named in `sections_degraded`); the overview never
500s. GET-only.

### React
`/workspace/command-center` (first Trading Workspace nav item). `useCommandCenter`
— one aggregated GET, 60 s hidden-paused refresh, `AbortController`, last-good
retained. Reuses `SectionCard` / `OpsMetric` / `OpsStatusTag`. No new dependency.

### Tests — `tests/test_stage15a_command_center.py` (10)
schema · canonical trace for daily/account/positions/alerts · determinism ·
degraded-section contract (monkeypatched failure → named, not fatal) · GET-only ·
no execution/broker state change · router binds no execution symbol.

### Gaps (documented)
XAUUSD news/economic-calendar engine not migrated (macro stage). Research-note /
snapshot **writing** not exposed (GET-only). `positions.py:34` NULL-`tp` latent
bug untouched (read defensively).

---

## 15B — Research Lab / adversarial audit  (`0c2b2fd`)

### Audit — `research_analytics.py`
Pure deterministic pandas/numpy. Inputs = trade-dict lists / DataFrames; outputs
= DataFrames / dicts of statistics. **No DB writes, no execution, no network.**
Functions: `calculate_trade_r_multiples`, `analyze_dimension_metrics`,
`analyze_liquidity_sources`, `analyze_sessions`, `analyze_confluence_calibration`,
`analyze_market_regimes`, `analyze_time_and_day`,
`stress_test_execution_sensitivity`, `monitor_expectancy_drift`,
`analyze_component_isolation`. Consumer: the Streamlit "GENERAL RESEARCH & EDGE
AUDIT" tab, which feeds a `backtester.run_backtest` result's trades through
these + `research_engine` (`BootstrapEstimator`, `ScorecardClassifier`,
`MultipleTestingTracker`). Distinct from `analytics.py` (Stage 14). Existing
coverage: `tests/test_research_lab.py`.

### Implementation
`POST /api/research/audit` (in the existing `research` router). Runs one
authoritative `backtester.run_backtest`, then applies the canonical functions
**verbatim** — 3-layer 60/20/20 split by trade index, bootstrap CI with fixed
seed 42, scorecard, execution stress, drift, and liquidity / session /
liquidity×session / regime / hour / day / confluence attribution. No formula
reimplemented.

- Validation: unknown tf/strategy/symbol → 422; `capital ≤ 0` → 422;
  `train_split` ∉ [0.1, 0.9] → 422; `< 4` trades → structured failure (never 500).
- POST-only (GET/PUT/DELETE → 405). Fail-closed
  `LiveTradingSafetyBarrier.assert_live_automation_disabled()`. Deterministic.
- `MultipleTestingTracker` (stateful data-mining ledger) **not** exposed —
  documented gap; stays in Streamlit.

### React
`/research/audit` (nav `research.audit`). `useResearchAudit` mirrors
`useBacktestRun` — POST fires only on the explicit "Run audit" click; never on
mount / re-render / StrictMode; `AbortController` + request-id guard; previous
result retained during a re-run. Output clearly labels observed / calculated /
interpretation. Reuses research primitives + `Sparkline` — no new dependency.

### Tests — `tests/test_stage15b_research_lab.py` (15)
validation · POST-only · response shape · canonical parity for
bootstrap/layer/stress · determinism · too-few-trades clean failure · no
execution/broker state change · router binds no execution symbol · canonical
`research_analytics` contract intact. **`tests/test_research_lab.py` unchanged
and passing.**

---

## 15C — Read-only Gemini AI Assistant  (`0f77d24`)

### Audit
`google-generativeai>=0.4.0` is in `requirements.txt` (installed 0.8.6) but
**unused** — no existing Gemini code. `ai_analysis.py` uses Ollama, not Gemini.
No AI chat API / UI. Secret pattern: `python-dotenv` + `os.getenv`.

### Architecture
```
React chat (/workspace/assistant)
  -> POST /api/ai/chat            api/routers/ai.py
    -> api/ai_context.py          allowlisted read-only snapshot
    -> api/gemini_client.py       server-side key, google-generativeai
    -> Gemini
```

### Security boundary
- The three AI modules bind **only** `api.ai_context` + `api.gemini_client`
  (plus the command-center read helpers for the snapshot). No import of / path
  to `execution_pipeline`, `broker_adapter`, `risk_gateway`, order submission or
  position mutation; nothing that could execute. Enforced by binding-level **and**
  import-graph tests.
- `GEMINI_API_KEY` / `GOOGLE_API_KEY` read from env; never returned.
  `/api/ai/status` reports only a boolean + model name. Unset key →
  `/api/ai/chat` returns `ok:false, error_kind:"not_configured"` HTTP 200
  (graceful); every other page still works.
- Fixed **server-side** system instruction (read-only; "never claim to have
  executed"; "never invent data"; distinguish fact / metric / finding /
  interpretation / general knowledge; unavailable data → say so). The
  authoritative snapshot is injected as a leading turn. User messages cannot
  override either — verified by a prompt-injection test.
- Execution-style prompts ("Buy EURUSD now", "Close my gold position", "Execute
  this strategy", "Modify my stop loss", "Enable live trading") → a text reply
  and **zero side effects**: `execution_orders` count, `mode_counts`,
  `open_positions`, `automation_enabled`, broker transmission all unchanged
  (parametrized test, stubbed provider).

### Context (allowlisted, bounded ~12 k chars, no raw trade history)
session + safety, daily + all-time performance
(`analytics.calculate_performance_metrics`), open-position summary, alert counts,
market regime / breadth, forward research state, watchlist highlights, recent
research notes. Unavailable sections are named, never guessed.

### Request validation
1–20 messages, ≤ 4000 chars each, ≤ 24000 total, last must be `user`,
`extra="forbid"` on request + message. Provider failures
(`provider_unavailable` / `timeout` / `rate_limit` / `empty`) → `ok:false` +
`error_kind`, never a 5xx or stack trace.

### React
`/workspace/assistant` (nav `workspace.assistant`) — suggestions, loading state,
per-message error + retry, clear conversation, Enter-to-send, capped history,
`AbortController`. No conversation persistence. No new dependency.

### Tests — `tests/test_stage15c_ai_assistant.py` (20)
request validation · POST-only · status returns no secret · not-configured
graceful 200 · AI modules bind no execution symbol · import graph has no
execution path · context build is read-only + bounded · (stubbed provider)
5 execution prompts → no side effects · system instruction + snapshot are
server-authored, not user-overridable · provider failure is graceful.

### Not exercised
A live end-to-end Gemini call (no API key in this environment). The full
request / response / failure plumbing is covered by stubbed-provider tests; set
`GEMINI_API_KEY` to enable the real call.

### Extensibility for future macro data
`ai_context.build_context()` is the single injection point — a future Macro
Intelligence source is added there without coupling `gemini_client` to any
provider.

---

## Regression (whole master stage)

| Gate | Result |
| :-- | :-- |
| Full suite `pytest tests/ -p no:randomly` | **1011 passed, 2 skipped, 0 failed** (was 967/2/0 at baseline; +45) |
| `tests/test_research_lab.py` | unchanged, passing |
| `npx tsc -b` | clean |
| `npm run build` | clean — 161 modules, 494.56 kB JS / 133.24 kB gzip |
| Browser smoke | 15A: 8 sections real data, 1 GET, 0 errors · 15B: mount fires nothing, Run → 1 POST 200 · 15C: not-configured shown gracefully, send disabled, execution prompt → 0 requests |
| Route regression | `/workspace`, `/workspace/{command-center,analytics,positions,alerts,assistant}`, `/research/{backtest,audit}`, `/operations{,/journal,/audit,/system}` — all load, 0 console errors, 0 exceptions |

## Safety

| Flag | Value |
| :-- | :-- |
| `/api/health.automation_enabled` | `false` (unchanged) |
| `live_broker_transmission` | `BLOCKED` (unchanged) |
| `execution_orders` total | 335 (unchanged from Stage 11 baseline) |
| `mode_counts` | `{LIVE: 81, SHADOW: 23, PAPER: 231}` (unchanged) |
| `open_positions` | 2 (unchanged) |
| `execution_pipeline` touched | no |
| `broker_adapter` touched | no |
| `risk_gateway` touched | no |
| Stage 11 audit/system cache | untouched |

## Streamlit

Untouched. `app.py`, `xauusd_daily_command_center.py`, `research_analytics.py`,
`research_engine.py`, `ai_analysis.py`, the `streamlit` dependency, and every
non-migrated workflow are unchanged. Command Center / Research Lab / analytical
AI are now covered by React/API; Streamlit retirement remains a separate
owner/roadmap decision.

## Known gaps

- XAUUSD news / economic-calendar engine — not migrated (macro stage).
- Command Center research-note / snapshot **writing** — not exposed (GET-only).
- `MultipleTestingTracker` (data-mining ledger) — not exposed (stateful).
- Live Gemini call — not exercised without an API key.
- `api/routers/positions.py:34` NULL-`tp` latent bug — out of scope, untouched.
