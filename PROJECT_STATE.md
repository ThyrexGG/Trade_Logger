# PROJECT STATE & ARCHITECTURAL RECORD
**TradeLogger Terminal — Living System Memory**
*Last Updated: 31 August 2026, Session 12 (Phase 20 XAUUSD True MTF Adversarial Verification & Paper/Shadow Audit Completed & Verified)*

> **HOW TO USE THIS FILE**
> Start any new AI session with: *"Read PROJECT_STATE.md and continue where we left off."*
> This file is the single source of truth for the project's current state.

---

## 1. What This Project Is

A professional-grade **trading research, journaling, and execution terminal** built for a liquidity-based, ICT/SMC methodology trader. It is NOT a simple trade log — it is a full research + execution stack:

- **Streamlit Desktop Terminal** (`app.py`) — primary UI, 9 tabs including dedicated **RESEARCH LAB** with USDJPY Reversal Lab (Phase 15), USDJPY Continuation Lab (Phase 16), USDJPY Edge Discovery Lab (Phase 17), USDJPY Conditional Validation Lab (Phase 18), True MTF Research Lab (Phase 19), and XAUUSD Adversarial Audit Lab (Phase 20), Execution Operations & System Health Panel, Pre-Trade Risk Preview, and Live Execution Controls (Strictly zero emojis across all UI tabs, buttons, metrics, and logs)
- **XAUUSD True MTF Adversarial Engine & Paper/Shadow Replayer** (`xauusd_audit_engine.py`) — 6 Execution Model Benchmark (15M vs 5M vs 1M FVG Limit), Structural SL Models (SL-A to SL-E) + 0.90x–1.10x Perturbation Sensitivity, Target Models A to F, 2D Parameter Perturbation Plateau (-20% to +20%), 10,000-Simulation Monte Carlo, and Canonical Execution Pipeline Replay (Paper & Shadow)
- **True Multi-Timeframe Strategy Engine & Best-Asset Discovery** (`true_mtf_engine.py`) — 1D Macro Bias $\to$ 4H Draw on Liquidity $\to$ 15M Setup $\to$ 5M Confirmation $\to$ 1M Precision Execution, 18-State Execution State Machine, Zero Lookahead Assertions, Standardized 16-Asset Discovery Universe
- **Strategy Edge Discovery & Research Engine** (`research_engine.py`, `research_analytics.py`, `usdjpy_research.py`, `usdjpy_continuation_research.py`, `usdjpy_edge_discovery.py`, `usdjpy_conditional_validation.py`) — Three-layer data partition (60% Train / 20% Validation / 20% Untouched Holdout), 95% Bootstrap Confidence Intervals, Cumulative Multiple Testing Tracker (108 hypotheses), 5,000-Iteration Permutation Test Engine, Rolling Walk-Forward Optimization, and Cost Sensitivity Stress Tester
- **Structured SMC / ICT Data Models & Context** (`strategies/smc_models.py`, `strategies/smc_utils.py`) — immutable dataclasses for LiquidityPools, FVGs, OrderBlocks, DealingRanges, and Multi-Timeframe SMCContext snapshots
- **Deterministic AI Market Analysis Engine** (`ai_analysis.py`) — 17-phase pipeline with structured SMC context prompt injection
- **Modular Strategy Framework** (`strategies/`) — unified engine for live + backtest with strict semver versioning (`strategy_version = "1.0.0"` / `"1.1.0"` / `"2.0.0"`)
- **Historical Backtester** (`backtester.py`) — OOS-split, SMC-aware, limit order aware, exact SL/TP/liquidity metadata tracking
- **Walk-Forward Optimization** (`wfo.py`) — rolling window parameter optimization
- **Broker Abstraction Layer** (`broker_adapter.py`) — normalized MT5, Capital.com, PaperAdapter & ShadowAdapter interface
- **Canonical Execution State Machine** (`execution_pipeline.py`) — 14-state deterministic order gateway with atomic mutex claims and in-flight risk reservations
- **Central Risk Gateway** (`risk_gateway.py`) — fail-closed, direction-aware correlation, broker floating daily loss, pre-trade risk calculator, in-flight reservation awareness
- **Broker Reconciliation Engine** (`reconciliation.py`) — singleton worker, discrepancy classification (MATCHED/LOCAL_ONLY/BROKER_ONLY/MISMATCH), UNKNOWN order resolution, startup crash recovery
- **Symbol Mapping & Specs** (`symbol_mapping.py`, `instrument_specs.py`) — canonical symbol mapping, lot size/step validator, fail-closed unknown ticker handling
- **System Health Evaluator** (`system_health.py`) — holistic live automation gating
- **FastAPI WebSocket server** (`server.py`) — live tick streaming + webhook receiver routed through canonical pipeline
- **Flutter mobile app** (`trade_logger_app/`) — companion mobile UI
- **Trade Journal** with screenshots, setup tags, ratings

---

## 2. Core Architecture

### Backend Files
| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit UI (9 tabs) + Research Lab (Reversal, Continuation, Edge Discovery, Conditional Validation, True MTF, XAUUSD Audit, XAUUSD Forward) + Operations Panel |
| `xauusd_forward_validator.py` | Phase 21 XAUUSD True MTF Frozen Strategy Engine, Forward Journal Persistence, Target Milestone (2R-7R) Analytics, Regime Monitor, Paper/Shadow Parity Checker |
| `research_explanations.py` | Centralized Explainable Research Module (Tooltips, Context-Aware Expectancy Overrides, Sample Tier Warnings, MTF Visual Flow, Drawdown Conversions) |
| `xauusd_audit_engine.py` | Dedicated XAUUSD True MTF Adversarial Audit Engine (6-Model Execution Benchmark, Structural SL Sensitivity, Parameter Perturbation Surface, 10k Monte Carlo, Canonical Pipeline Replayer) |
| `true_mtf_engine.py` | Dedicated True Multi-Timeframe (1D->4H->15M->5M->1M) Engine, 18-State Machine, Execution Timeframe Comparer, 16-Asset Discovery Universe |
| `usdjpy_conditional_validation.py` | Dedicated USDJPY Regime-Conditional Validation Engine (5,000-Run Permutation Tester, 5,000-Run Monte Carlo, Rolling WFO, Multi-Testing Ledger) |
| `usdjpy_edge_discovery.py` | Dedicated USDJPY 27-Condition Mechanical Discovery Engine, Regime Classifier, Deep Excursion Analyzer, Holding-Time Profiler, Trend Persistence Map |
| `usdjpy_continuation_research.py` | Dedicated USDJPY 12-Condition Trend-Continuation Ablation Suite, Directional/Session diagnostics, MAE/MFE Profiler, Mechanical Baselines |
| `usdjpy_research.py` | Dedicated USDJPY 12-Condition Reversal Ablation Suite, Directional/Session diagnostics, MAE/MFE Profiler, Mechanical Baselines |
| `research_engine.py` | 3-Layer Splitter (Train/Val/Holdout), Multiple Testing Tracker, Bootstrap 95% CI Estimator, Scorecard Classifier |
| `research_analytics.py` | Liquidity Source Attribution, Session Matrix, Confluence Calibration Curve, Execution Stress, Drift Monitor |
| `server.py` | FastAPI REST + WebSocket server + webhook receiver (Canonical Order Routed) |
| `database.py` | SQLite + PostgreSQL multi-tenant DB with thread-safe queries & test WAL mode |
| `market_data.py` | Live data fetching, bid/ask ticks, liquidity, FVG, OB, confluence |
| `symbol_mapping.py` | Master canonical symbol normalization, suffix trimming, broker translation |
| `instrument_specs.py` | Instrument specs registry (digits, ticks, lot steps, min/max volume validator) |
| `system_health.py` | Comprehensive live automation health evaluator & safety gate |
| `ai_analysis.py` | 17-phase AI/deterministic analysis pipeline with SMCContext summary |
| `trade_setup_engine.py` | Live deterministic strategy evaluator |
| `backtester.py` | Historical simulation engine |
| `wfo.py` | Walk-Forward Optimization engine |
| `analytics.py` | Win rate, PF, SQN, drawdown, attribution analytics |
| `broker_adapter.py` | Normalized broker abstraction (MT5, Capital.com, PaperAdapter, ShadowAdapter) |
| `execution_pipeline.py` | Canonical State Machine (14 states, atomic DB mutex claims, in-flight risk reservations, crash recovery) |
| `risk_gateway.py` | Central Risk Gateway (Fail-closed, Directional Correlation, Floating Daily Loss, Pre-Trade Risk Calculator, In-Flight Risk Ledger) |
| `reconciliation.py` | Background reconciliation worker lifecycle, discrepancy detection, UNKNOWN resolver |
| `account_state.py` | Broker-reconciled account state fetching |
| `paper_simulator.py` | Continuous paper execution simulator |

### Strategy Framework (`strategies/`)
| File | Purpose |
|------|---------|
| `base.py` | `BaseStrategy` abstract class — unified schema |
| `usdjpy_smc_continuation.py` | USDJPY SMC Trend Continuation: 4H Bias -> Counter-trend Sweep -> 15m BOS -> FVG Entry (`strategy_version = "1.0.0"`) |
| `smc_models.py` | Structured immutable dataclasses: `LiquidityPool`, `FairValueGap`, `OrderBlock`, `DealingRange`, `MarketStructureEvent`, `SMCContext` |
| `__init__.py` | Registry: `get_strategy()`, `get_all_strategy_names()` |
| `smc_utils.py` | Vectorized SMC: Swings, FVG, Sessions, PDH/PDL, PWH/PWL, Asian range, EQH/EQL, Dealing Range, Structured Extractors |
| `ict_2022_model.py` | ICT 2022: SSL/BSL Sweep → MSS → FVG retracement (`strategy_version = "1.1.0"`) |
| `liquidity_sweep.py` | Liquidity Sweep Reversal (immediate sweep entry, `strategy_version = "1.1.0"`) |
| `trend_continuation.py` | EMA crossover continuation |
| `mean_reversion.py` | RSI extreme reversal |

### Automated Test Suite Status (146 PASSED, 2 SKIPPED — 100% REGRESSION PASS RATE)
| File | Purpose | Test Count |
|------|---------|------------|
| `test_xauusd_forward_validation.py` | Forward journal persistent logging, R milestone hit rates (2R-7R), dataset isolation, pipeline parity, regime non-interference | 6 PASSED |
| `test_research_explanations.py` | Metric catalog completeness, tooltips, sample tier rules, CI interpretation, context overrides, drawdown, Monte Carlo, zero emojis/certainty | 9 PASSED |
| `test_phase20_mtf_integrity.py` | Adversarial future mutation lookahead proof, timestamp strictness, SL/TP models, perturbation plateau, paper/shadow replay parity | 11 PASSED |
| `test_true_mtf_research.py` | 18-state lifecycle, zero-lookahead assertions, 1M vs 5M vs 15M benchmark, cross-asset ranking | 5 PASSED |
| `test_usdjpy_conditional_validation.py` | Mathematical auditor, subgroup metrics, permutation reproducibility, WFO, Monte Carlo, cost stress | 9 PASSED |
| `test_usdjpy_edge_discovery.py` | USDJPY 27-condition catalog, regime classifier, deep excursion, holding times, day-of-week, persistence | 5 PASSED |
| `test_usdjpy_continuation.py` | USDJPY 12 continuation ablation configs, directional bias, MAE/MFE excursion, mechanical baselines | 5 PASSED |
| `test_usdjpy_research.py` | USDJPY 12 reversal ablation configs, directional bias, MAE/MFE profit giveback, mechanical baselines | 5 PASSED |
| `test_research_lab.py` | 3-layer split, bootstrap reproducibility, multiple testing counter, scorecard, R-normalization, liquidity/session matrix, confluence curve | 8 PASSED |
| `test_smc_models.py` | SMC structured models, CE, MT, Premium/Discount, IFVG, Pre-Trade Risk Preview | 5 PASSED |
| `test_symbol_mapping.py` | Canonical symbol normalization, aliases, suffixes, broker translation | 5 PASSED |
| `test_instrument_specs.py` | Instrument specifications, lot step alignment, min/max volume limits | 7 PASSED |
| `test_reconciliation_worker.py` | Worker lifecycle, health states (`HEALTHY`, `STOPPED`), health gate | 3 PASSED |
| `test_price_side_execution.py` | Bid/Ask side correctness, price deviation threshold gating | 1 PASSED |
| `test_paper_shadow_parity.py` | Paper vs Shadow decision parity, zero database pollution in Shadow | 2 PASSED |
| `test_execution_recovery.py` | Crash/restart recovery of unsubmitted orders to `FAILED_SAFE` | 1 PASSED |
| `test_execution_concurrency.py` | 20 simultaneous threads atomic claim, in-flight portfolio risk ledger | 2 PASSED |
| `test_account_risk.py` | Risk limits, floating daily loss breach, portfolio aggregate risk | 4 PASSED |
| `test_broker_reconciliation.py` | Discrepancy matrices (MATCHED, LOCAL_ONLY, BROKER_ONLY, MISMATCH) | 5 PASSED |
| `test_execution_state_machine.py` | 14-state transitions, persistence, signal_id idempotency | 4 PASSED |
| `test_failure_injection.py` | Broker timeouts to UNKNOWN, reconciliation to FILLED/NOT_FILLED, kill switch | 7 PASSED |
| `test_execution_safety.py` | Core execution safety, webhook HMAC, payload validation, future ts rejection | 20 PASSED |
| `test_paper_execution.py` | End-to-end paper and shadow execution pipelines | 3 PASSED |
| `test_mtf_validation.py` | MTF lookahead proof, future candle mutation, bias audit | 4 PASSED |
| `test_monte_carlo.py` | Monte Carlo probability expectancy distributions | 2 PASSED |
| `test_phase11.py` | Portfolio risk exposure, simulator fills, signal attribution | 3 PASSED |
| `test_wfo.py` | Walk-forward optimization windows | 1 PASSED |
| `tests/integration/test_mt5_adapter.py` | MT5 live read-only verification (Truthfully SKIPPED/BLOCKED when terminal closed) | 1 SKIPPED |
| `tests/integration/test_capitalcom_adapter.py` | Capital.com live read-only verification (Truthfully SKIPPED/BLOCKED when API offline) | 1 SKIPPED |

---

## 3. Execution Pipeline Architecture (Phase 9-10)

### Canonical Order Flow
```
WEBHOOK / SIGNAL
      ↓
CANONICAL PIPELINE (execution_pipeline.py)
      ↓
RISK ENGINE (portfolio_risk.py)
      ↓
BROKER API (order_execution.py)
```

### Safety Controls
- **Fail-Closed Principle**: Database unavailable → Cannot verify risk → DO NOT TRADE
- **Persistent Idempotency**: SQLite-backed signal_id deduplication (survives restart)
- **Kill Switch**: Global `KILL_SWITCH` flag halts all automated execution
- **Execution State Machine**: `PENDING → SUBMITTED → FILLED | REJECTED | UNKNOWN`
- **Stale Signal Protection**: Signals older than 300s are rejected
- **HMAC Webhook Signing**: Cryptographic verification of inbound webhooks
- **Execution Modes**: `SHADOW` (log only) → `PAPER` (simulated) → `LIVE` (real money)

### Risk Controls (portfolio_risk.py)
- Max daily loss: 3% of account equity (uses broker-reported floating PnL)
- Max total open risk: 15% of equity
- Max symbol exposure: 2 positions per instrument
- Max directional exposure: 4 positions in same direction
- Correlated asset rejection: >0.80 correlation threshold

---

## 4. Strategy Framework — Critical Design Decisions

### Unified Execution Model
Both `trade_setup_engine.py` (live) and `backtester.py` (historical) call `strategy.analyze(df, current_index, context)` from the same registry. Zero duplicated logic.

### BaseStrategy Output Schema
```python
{
    "status": "READY" | "WATCHING" | "WAITING" | "NO TRADE" | "INVALIDATED",
    "setup": "LONG" | "SHORT" | "N/A",
    "execution_model": "MARKET" | "LIMIT" | "N/A",
    "expiration_bars": int,
    "entry_zone": str,
    "ideal_entry": float | "N/A",
    "stop_loss": float | "N/A",
    "tp1": float | "N/A",
    "tp2": float | "N/A",
    "risk_reward": str,
    "trigger": str,
    "invalidation": str,
    "confidence": "Low" | "Medium" | "High",
    "setup_quality": "A+" | "A" | "B" | "C",
    "liquidity_type": str,
    "session": "ASIA" | "LONDON" | "NEW_YORK" | "N/A",
    "reason": str
}
```

### SMC Features in `smc_utils.add_smc_features(df)`
- **Swing Highs/Lows**: confirmed only after `swing_length` bars — no look-ahead bias
- **FVGs**: Bullish `Low(t) > High(t-2)`, marked at bar `t` only — no look-ahead
- **PDH/PDL**: `daily_highs.shift(1)` mapped back to df — strictly previous day
- **Asian Range**: Only populated after 06:00 UTC — uses yesterday's range during Asia session
- **Session flags**: `is_asia` (00-06 UTC), `is_london` (07-16 UTC), `is_ny` (12-20 UTC)
- **Column normalization**: All OHLC normalized to Title Case at entry
- **Liquidity sweep priority**: PDH/PDL > Asian Range > Fractal Swings

### Backtester Execution
- `MARKET`: fill at next bar Open + slippage
- `LIMIT`: fill when Low/High touches `ideal_entry`, gap-fill at Open if price gaps through
- Expiry: uses `setup['expiration_bars']`, defaults to 10
- Do NOT `df.dropna()` after SMC features — NaN is intentional for non-FVG bars

---

## 5. Known Bugs Fixed (Do Not Reintroduce)

| Bug | Fix |
|-----|-----|
| `KeyError: 'High'` on live data | `smc_utils.py` normalizes OHLC column names at entry |
| `TypeError: 'Timestamp' cannot be integer` | Use `df.index.get_loc(last_fvg_idx)` for `iloc` |
| `TradeSetupEngine unexpected kwarg 'strategy_name'` | Stale `.pyc` — clear `__pycache__` |
| `df.dropna()` wiping df after SMC features | Changed to `dropna(subset=['Open','High','Low','Close'])` |
| AI analysis running on every Streamlit rerun | Gated behind `▶ RUN ENGINE` button with `st.session_state` cache |
| Orphaned Streamlit process on port 8501 | `Get-Process python \| Stop-Process -Force` then restart |
| **`st.stop()` in AI tab blanking all downstream tabs** | **Replaced with `if/elif/else` branching (no `st.stop()`)** |
| **CSS hiding sidebar expand arrow** | **Removed `[data-testid="stHeader"]` from `display:none` rule** |
| **CSS hiding loading spinner/status widget** | **Removed `.stSpinner > div:first-child { display:none }` and `stStatusWidget` hiding** |

---

## 6. UI Tab Structure (app.py)

| Tab | Key Feature |
|-----|-------------|
| Analytics & Overview | Account metrics, equity curve, position table, calendar |
| Trading Workspace | Live chart, drawing tools, order execution panel |
| AI Market Context | `▶ RUN ENGINE` button → runs selected strategy on live data |
| Trade Journal | Per-trade journal with screenshots, setup tags, ratings |
| Price Alerts | Threshold alert management, risk studio |
| Quick Terminal | Quick order execution interface |
| Sandbox | Strategy selection, parameters, OOS backtest, equity curve |
| System Health & Paper | Component status, paper execution monitoring |

**Important**: AI Market Context tab runs analysis ONLY on button press — not on every page load. Result cached by `AI_CACHE_KEY = f"ai_data_{symbol}_{tf}_{strategy}"`.

**Important**: The AI tab must NEVER use `st.stop()` — it halts the entire script and blanks all subsequent tabs.

---

## 7. AI Analysis Pipeline (17 Phases)

1. Live OHLC data fetch (MT5 → Binance → Yahoo Finance fallback)
2. ML Random Forest edge scoring (3-class: BUY/SELL/NEUTRAL)
3. Data quality normalization
4. MTF alignment math
5. Volatility regime (ADX)
6. Volume Profile (POC/VAH/VAL + Session VWAP)
7. Market structure (BOS/MSS + swings)
8. Liquidity engine (BSL/SSL geometry)
9. FVG mitigation engine
10. Order Block detection
11. Session engine (Asian range)
12. Macro/news risk
13. COT engine
14. Cross-asset correlation (DXY)
15. Confluence engine → Bullish/Bearish/Neutral bias
16. Trade Scenario Engine → routes to Modular Strategy Framework
17. Final validation (macro + session sanity check)

---

## 8. Phase Completion Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1-5 | Core UI, Broker Sync, Analytics, AI Pipeline | ✅ COMPLETE |
| Phase 6 | Modular Strategy Framework | ✅ COMPLETE |
| Phase 7 | Multi-Timeframe Strategy Engine | ✅ COMPLETE |
| Phase 7.5 | MTF Validation | ✅ COMPLETE |
| Phase 8 | Walk-Forward Optimization + Monte Carlo | ✅ COMPLETE |
| Phase 9 | Production Execution, Risk & Safety | ✅ COMPLETE |
| Phase 9.5 | Execution Safety Audit (28/28 tests) | ✅ COMPLETE |
| Phase 10 | Broker-Reconciled Risk & Paper-to-Live | ✅ COMPLETE |
| Phase 11 | Live Paper Validation & Portfolio Research | ✅ COMPLETE |
| Phase 11.5 | Code Integrity Audit & UX Fixes | ✅ COMPLETE |
| Phase 12A | Execution State Machine, Risk Gateway & Reconciliation | ✅ COMPLETE |
| Phase 12B | Broker Integration, Concurrency, Parity & Shadow Validation | ✅ COMPLETE (41 Passed / 2 Blocked) |

---

## 9. Database Schema Summary

| Table | Key Columns |
|-------|-------------|
| `closed_trades` | `trade_id`, `account_id`, `symbol`, `direction`, `volume`, `entry_price`, `exit_price`, `commission`, `swap`, `gross_profit`, `net_profit`, `entry_time`, `exit_time`, `duration_minutes`, `setup_tag`, `chart_snapshot_url`, `notes`, `rating` |
| `raw_deals` | `deal_id`, `account_id`, `symbol`, `type`, `volume`, `price`, `commission`, `swap`, `profit`, `timestamp`, `position_id` |
| `open_positions` | `position_id`, `account_id`, `symbol`, `direction`, `volume`, `entry_price`, `current_price`, `sl`, `tp`, `floating_pnl`, `swap`, `open_time`, `updated_at` |
| `price_alerts` | `alert_id`, `symbol`, `target_price`, `condition`, `is_active`, `created_at`, `triggered_at`, `notes` |
| `trade_journal` | `trade_id`, `notes`, `strategy`, `rating`, `screenshot_path`, `updated_at` |
| `app_settings` | `key`, `value` |
| `chart_drawings` | `symbol`, `drawings_data`, `updated_at` |
| `received_signals` | `signal_id`, `order_id`, `strategy`, `timeframe`, `setup_type`, `confluence`, `session`, `signal_outcome` |
| `execution_audit_log` | `signal_id`, `symbol`, `direction`, `volume`, `status`, `broker_order_id`, `execution_mode`, `timestamp` |
| `correlation_matrix` | `symbol_a`, `symbol_b`, `correlation`, `window`, `updated_at` |

---

## 10. Design System Tokens

| Token | Value |
|-------|-------|
| Background | `#0a0e17` / `#0c0f16` |
| Cards | `#0e131f` / `#131722` |
| Bullish / Highlight | `#00ffcc` |
| Bearish / Loss | `#ff5555` |
| Warning / Gold | `#f59e0b` |
| Growth / Secondary | `#bef264` |
| Font | Inter + monospace numbers |

---

## 11. Defaults

- **Default symbol**: USDJPY (XAUUSD secondary)
- **Default timeframe**: 15m
- **Default strategy**: ICT 2022 Model
- **Default risk per trade**: 1%
- **Data source priority**: MT5 → Binance (crypto) → Yahoo Finance

---

## 12. How to Run

```powershell
# Start Streamlit Terminal
cd C:\Users\Thyrex 2.0\Desktop\Trade_Logger
python -m streamlit run app.py --server.port 8502

# Start FastAPI Server (for webhooks)
python server.py

# Stop all Python processes
Get-Process python | Stop-Process -Force
```

---

## 13. Next Priorities & Evolution (Phase 13 → Phase 14)

1. **MT5 Demo / Live Auto-Trading Execution**:
   - **Webhook Mode**: Route incoming TradingView alerts (`/webhook`) directly to MT5 terminal (`broker: "MT5"`) with canonical risk checks, dynamic lot sizing, and floating daily loss gates.
   - **Autonomous Strategy Scanner Loop**: Optional background worker to continuously scan live candles (1m/5m/15m) for ICT 2022 / Liquidity Sweep setups and auto-dispatch orders directly to MT5 Demo.
2. **WebHook Trading Automation Payload Endpoints & Secret Security**:
   - Fine-tune HMAC signature validation and automated alert format documentation.
3. **Live Walk-Forward / Paper-to-Live Divergence Monitoring**:
   - Track slippage, latency, and fill price divergence between Paper simulation and MT5 Demo executions.
4. **Institutional Trade Setup Visualization**:
   - Dynamic Fibonacci OTE overlays, FVG boxes, and dealing range equilibrium markers plotted directly on the interactive TradingView canvas in `app.py`.

