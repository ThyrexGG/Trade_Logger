# STAGE 14 — Analytics Migration

**Roadmap reference:** `docs/STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md` §11 —
migration unit 3 of 4 ("`GET /api/analytics/*` + React Analytics page —
read-only pass-through of `analytics.py`").
**Baseline commits:** `6c53633` (Stage 12), `8f32029` (Stage 13)
**Date:** 2026-09-03
**Scope:** the Streamlit "ANALYTICS & OVERVIEW" tab (`analytics.py`-driven).
Not in scope: the research-analytics adversarial-audit tab
(`research_analytics.py` — a Research Lab workflow), the "Sync MT5 / Sync
Capital" data-ingestion buttons, Daily Command Center, AI Assistant, paper
execution.

---

## 1. Original Streamlit Analytics capabilities (`app.py:1882–2470`)

### Inputs / filters
| Control | Behaviour |
| :-- | :-- |
| Account selector | `ALL` or a specific `account_id`; filters `df_trades` by `account_id` |
| Symbol multiselect | options = `acc_filtered_df["symbol"].unique()`, default all |
| Date range | on `exit_time`; `min`/`max` derived from the account-filtered data; end is inclusive (`< end + 1 day`) |
| Starting balance | `number_input`, per-account UI default, `min 10.0` |
| Sync MT5 / Sync Capital buttons | **data ingestion, not analytics** — out of scope |

### Metrics (all from `analytics.calculate_performance_metrics(filtered_df, initial_balance)`)
Account balance (broker balance if known, else `final_balance`), `gain_pct`,
`total_net_pnl`, `profit_factor`, `total_gross_profit`, `total_gross_loss`,
`max_drawdown_pct`, `max_drawdown_usd`, `peak_balance`, `win_rate`,
`winning_trades` / `losing_trades` / `break_even_trades` / `total_trades`,
`sqn`, `avg_duration_minutes` (→ hold-time string), `best_trade` / `worst_trade`,
`avg_win` / `avg_loss` / `win_loss_ratio`, `expectancy`, `long_stats` /
`short_stats`, `best_symbols` / `worst_symbols`.

### Derived series / visuals (computed inline in `app.py`, not in `analytics.py`)
| Element | Data | Migrated as |
| :-- | :-- | :-- |
| Account balance curve | `initial_balance + net_profit.cumsum()` over `exit_time`; Streamlit adds a synthetic −12h baseline point + Hermite spline (presentation) | real (time, equity) anchor points → `Sparkline` (no synthetic point, no spline) |
| Performance radar | 5 scores (`score_pnl`, `score_wr`, `score_pf`, `score_dd`, `score_sqn`) derived from metrics | same 5 scores → horizontal "Performance index" bars |
| Avg win/loss + long/short ratio bars | from metrics / counts | "Direction split" cells + metric cards |
| Period returns (D / W / M / Y) | daily mean, 7-day, 30-day windows vs `now`; annualized = `(1+daily)^252` | `period_returns` block (same formulas, windows relative to now) |
| Monthly calendar heatmap | `month_trades.groupby(exit_time.dt.day)` | **not ported as a grid** — daily P&L exposed as `daily_pnl` and shown as a bar series |
| Net Profit by Symbol (bar) | `groupby("symbol")["net_profit"].sum()` | `symbol_breakdown` → bar rows |
| Net Profit by Strategy Tag (bar) | `groupby("setup_tag").sum()` (NaN → "Untagged") | `tag_breakdown` → bar rows |

### Data sources
`database.get_closed_trades()` (the `closed_trades` table; `entry_time` /
`exit_time` parsed with `pd.to_datetime(..., format="mixed", utc=True).dt.tz_localize(None)`)
and `database.get_account_balances()` for the official broker balance.

### Caching
`calculate_performance_metrics` is a pure deterministic function (no cache, no
side effects). `get_closed_trades(ttl_sec)` has a short TTL cache. Streamlit
recomputes on every rerun.

---

## 2. Analytics modules / functions reused

| Reused verbatim | From |
| :-- | :-- |
| `analytics.calculate_performance_metrics(df, initial_balance)` | `analytics.py` — **every headline metric**; no formula reimplemented |
| `database.get_closed_trades(ttl_sec=5.0)` | `database.py` |
| `database.get_account_balances()` | `database.py` |
| date parsing pattern (`format="mixed", utc=True`, tz-strip) | copied from `app.py:1543` so the filtered population is byte-identical |

The router only **filters** the population and **shapes** derived series
(equity anchors, daily/symbol/tag aggregation, period returns). `research_analytics.py`
is **not imported** (verified by test).

---

## 3. API — `GET /api/analytics/performance`

Single aggregated endpoint (the Streamlit surface is one analytical view).
GET-only; `POST` / `PUT` / `DELETE` → `405`.

### Query parameters
| Param | Type | Rules | Default |
| :-- | :-- | :-- | :-- |
| `account` | string | must be a known `account_id` or `ALL` → else `422` | `ALL` |
| `symbols` | CSV | each must be in the account-filtered population's symbol set → else `422` | all |
| `start` | `YYYY-MM-DD` | parseable date → else `422`; filters `exit_time >= start` | — |
| `end` | `YYYY-MM-DD` | parseable date → else `422`; filters `exit_time < end + 1 day` (inclusive) | — |
| `initial_balance` | float | `> 0`, finite → else `422` | `10000.0` |

`start > end` → `422`.

### Response `AnalyticsPerformanceResponse`
```
metrics: PerformanceMetrics          # faithful mirror of calculate_performance_metrics
equity_curve: EquityAnchor[]         # real (time, equity, net_profit, symbol), ≤400 (decimated, first+last kept)
equity_curve_sampled: bool
daily_pnl: DailyPnl[]                # {date, net_profit, trades}
symbol_breakdown: SymbolBreakdownRow[]   # {symbol, net_profit, trades, wins, win_rate}, sorted by net_profit desc
tag_breakdown: TagBreakdownRow[]     # {setup_tag, net_profit, trades} (NaN/"" → "Untagged")
period_returns: PeriodReturns        # {avg_daily_pct, weekly_pct, monthly_pct, annualized_pct, weekly_pnl, monthly_pnl}
official_balance: float | null       # broker balance for the account (sum for ALL), or null
filters_applied: {account, symbols, start, end, initial_balance}
available: {accounts, symbols, date_min, date_max}   # populates the filter UI from the same response
matched_trades: int
source: "closed_trades"
live_broker_transmission: "BLOCKED"
timestamp: ISO-8601
```

One request per filter set; `available` ships in every response so no separate
"filter options" call is needed (no N+1).

---

## 4. React route — `/workspace/analytics`

New nav item `workspace.analytics` ("Analytics", `ChartIcon`) under Trading
Workspace. `AnalyticsPage` + `components/analytics/AnalyticsControls.tsx`
(account / symbol chips / date range / starting balance) + `AnalyticsView.tsx`
(metric cards, equity `Sparkline`, period returns, symbol & tag P&L bars,
direction split, performance-index bars, daily P&L bar series).

- `useAnalytics(query)` — one aggregated GET; filter changes **debounced 300ms**
  (a multi-select or date drag → a single request); previous request aborted on
  every change; last-good data kept during refetch and on a rejected filter
  (`422` shows a warning strip, keeps the prior result). **No polling.**
- No new dependency — reuses the existing `Sparkline` (research primitives) and
  hand-rolled SVG/`div` bars. No calculation in the browser: `AnalyticsView`
  only formats numbers the API already computed (formatting helpers are in
  `lib/format.ts`, clearly separate).
- No Buy/Sell/Execute control (verified by browser scan).

---

## 5. Parity matrix

| Streamlit element | React / API | Status |
| :-- | :-- | :-- |
| Account / symbol / date / balance filters | same 4 filters (query params) | **FULLY_REPLACED** |
| All `calculate_performance_metrics` headline metrics | `metrics` block (exact mirror) | **FULLY_REPLACED** — byte-parity verified |
| Account balance curve | `equity_curve` → `Sparkline` | **FULLY_REPLACED (data)** — Hermite spline + synthetic −12h baseline point are presentation-only and intentionally dropped |
| Period returns D/W/M/Y | `period_returns` | **FULLY_REPLACED** (windows relative to now, same as Streamlit) |
| Net P&L by symbol / by tag | `symbol_breakdown` / `tag_breakdown` → bars | **FULLY_REPLACED** |
| Long/short + avg win/loss ratio bars | direction-split cells + metric cards | **FULLY_REPLACED (data)** |
| Performance radar (5 scores) | 5 "Performance index" bars | **PRESENTATION DIFFERENCE** — same scores, bars instead of a radar polygon |
| Monthly calendar heatmap | `daily_pnl` bar series | **PARTIAL** — daily P&L data is exposed and charted; the month-grid calendar widget is not reproduced |
| Sync MT5 / Sync Capital buttons | — | **OUT OF SCOPE** — data ingestion, not analytics; stays in Streamlit |
| Research analytics (R-multiples, exec-stress, confluence, drift) | — | **OUT OF SCOPE** — different tab (`research_analytics.py`), a Research Lab unit |

### Parity verification (fixed dataset: 53 closed trades, 2 accounts, USDJPY+XAUUSD)
`test_stage14_analytics.py::test_metrics_match_canonical_function` recomputes the
exact filtered population and asserts **equality** (not tolerance) on 18 metric
fields plus `long_stats` / `short_stats` / `best_symbols`, unfiltered and under
account / symbol / date filters. Browser QA confirmed the React page shows the
same numbers (`-$357.15` net P&L, `$9,944.79` balance, `$851.43` gross profit).
Equity-curve traceability: `last equity == initial_balance + total_net_pnl`
(±0.02 rounding).

**Intentional presentation-only differences:** spline smoothing + synthetic
baseline point on the equity curve; radar → bars; calendar grid → bar series.
No numerical difference.

---

## 6. Known gaps

- **Monthly calendar grid** — not reproduced as a widget (daily P&L data is
  available via `daily_pnl` and shown as a bar series). Add later if wanted.
- **Per-account starting-balance memory** — Streamlit remembers a per-account
  default in session state; the API default is a flat `10000` (the
  `analytics.py` default). The user sets it explicitly in the field.
- **Sync buttons** — deliberately not migrated (ingestion, not analytics).
- **Research analytics** — separate Research Lab migration unit.

---

## 7. Performance behaviour

- One aggregated GET per filter set; `available` piggybacks so there is no
  second "options" request. No N+1.
- Filter changes debounced 300ms → a single request after a burst of toggles.
- `AbortController` cancels the superseded request on every change/unmount.
- Raw trade history is **not** sent to the browser — only aggregates + a
  ≤400-point decimated equity curve.
- Backend: `get_closed_trades(ttl_sec=5.0)` short TTL cache; `calculate_performance_metrics`
  is O(n) over the filtered frame. On the 53-trade dataset the endpoint responds
  in a few ms. No caching layer added (consistent with the pure function); the
  Stage 11 audit/system cache work is untouched.

---

## 8. Safety verification

| Check | Result |
| :-- | :-- |
| endpoint methods | GET only; `POST`/`PUT`/`DELETE` → `405` |
| `execution_pipeline` / `broker_adapter` / `risk_gateway` / order files touched | **none** (`git diff`) |
| `api.routers.analytics` namespace binds an execution/broker/`research_analytics` symbol | **no** (test) |
| `/api/health.automation_enabled` after analytics use | `false` (unchanged) |
| `live_broker_transmission` | `BLOCKED` (unchanged) |
| `execution_orders` count / `mode_counts` after repeated analytics calls | unchanged |
| `open_positions` | unchanged |
| React page execution controls | **0** (browser scan) |
| network methods from the page | **GET only** (browser scan) |

---

## 9. Test results

**`tests/test_stage14_analytics.py`** (19 cases): response shape + source ·
metrics equal the canonical function (unfiltered + account/symbol/date) · empty
population → zeroed metrics · date filter narrows to the canonical count ·
symbol / account filters match canonical · 7 invalid-filter cases → `422` ·
deterministic (two calls identical) · equity-curve traceability · GET-only ·
no execution/broker state change · router binds no execution symbol · canonical
`analytics.py` contract not weakened.

| Gate | Result |
| :-- | :-- |
| Full suite `pytest tests/ -p no:randomly` | **967 passed, 2 skipped, 0 failed** (was 948/2/0; +19) |
| `test_research_lab.py` (`research_analytics`) | pass (unaffected) |
| `npx tsc -b` | clean |
| `npm run build` | clean — 151 modules, 462.07 kB JS / 125.87 kB gzip |
| Browser smoke `/workspace/analytics` | loads, real data, sparkline, symbol filter → 1 debounced GET (matched 50), date filter → 1 GET, `start>end` → `422` + warning strip + last-good retained; 0 console errors, 0 exceptions, GET-only, no execution request |
| Browser regression | `/workspace`, `/workspace/positions`, `/workspace/alerts`, `/operations{,/journal,/audit,/system}` all load clean |

No frontend unit-test infra in `frontend/` — covered by the CDP browser smoke.

---

## 10. Remaining Streamlit-only workflows

- **Research Lab** — True MTF lab, USDJPY empirical labs, edge discovery,
  `research_analytics.py` adversarial audit.
- **Daily Command Center** — preflight, session context, research-journal notes.
- **AI Market Context** — `ai_analysis` + Ollama.
- **Manual paper/shadow order entry** — Quick Terminal (only with explicit
  execution-scope authorization).
- **Analytics "Sync MT5 / Sync Capital"** data-ingestion buttons; the custom
  notification-rules engine (from Stage 13); the month-calendar widget.

Analytics performance reporting is now covered by React/API. Streamlit
retirement stays a separate owner/roadmap decision.

**Pre-existing latent bug (still out of scope):** `api/routers/positions.py:34`
unguarded `float(pos.get("tp", 0.0))` on a NULL `tp`.

---

## 11. Files changed

| File | Change |
| :-- | :-- |
| `api/schemas.py` | `+SymbolPnl`, `+DirectionStats`, `+PerformanceMetrics`, `+EquityAnchor`, `+DailyPnl`, `+SymbolBreakdownRow`, `+TagBreakdownRow`, `+PeriodReturns`, `+AnalyticsFiltersEcho`, `+AnalyticsAvailable`, `+AnalyticsPerformanceResponse` |
| `api/routers/analytics.py` | **new** — `GET /api/analytics/performance` |
| `api/main.py` | register `analytics.router` (no CORS change — GET only) |
| `frontend/src/types/analytics.ts` | **new** |
| `frontend/src/api/analytics.ts` | **new** — `getAnalyticsPerformance` |
| `frontend/src/lib/useAnalytics.ts` | **new** — one aggregated GET, 300ms debounce, abortable |
| `frontend/src/components/analytics/AnalyticsControls.tsx` | **new** |
| `frontend/src/components/analytics/AnalyticsView.tsx` | **new** |
| `frontend/src/pages/AnalyticsPage.tsx` | **new** — `/workspace/analytics` |
| `frontend/src/lib/navigation.ts` | `+workspace.analytics` nav item |
| `frontend/src/App.tsx` | route `workspace.analytics` → `AnalyticsPage` |
| `tests/test_stage14_analytics.py` | **new** — 19 cases |
| `docs/STAGE_14_ANALYTICS_MIGRATION.md` | **new** — this document |
| `PROJECT_STATE.md` | `+§9.5`; header → Session 44 |
