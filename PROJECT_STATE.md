# PROJECT STATE & ARCHITECTURAL RECORD
**TradeLogger Terminal — Living System Memory**
*Last Updated: 30 August 2026*

> **HOW TO USE THIS FILE**
> Start any new AI session with: *"Read PROJECT_STATE.md and continue where we left off."*
> This file is the single source of truth for the project's current state.

---

## 1. What This Project Is

A professional-grade **trading research and journaling terminal** built for a liquidity-based, ICT/SMC methodology trader. It is NOT a simple trade log — it is a full research stack:

- **Streamlit Desktop Terminal** (`app.py`) — primary UI, 6 tabs
- **Deterministic AI Market Analysis Engine** (`ai_analysis.py`) — 17-phase pipeline
- **Modular Strategy Framework** (`strategies/`) — unified engine for live + backtest
- **Historical Backtester** (`backtester.py`) — OOS-split, SMC-aware, limit order aware
- **MT5 + Capital.com broker sync** — live position tracking
- **FastAPI WebSocket server** (`server.py`) — live tick streaming
- **Flutter mobile app** (`trade_logger_app/`) — companion mobile UI
- **Trade Journal** with screenshots, setup tags, ratings

---

## 2. Core Architecture

### Backend Files
| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit UI (6 tabs) |
| `server.py` | FastAPI REST + WebSocket server |
| `database.py` | SQLite + PostgreSQL multi-tenant DB |
| `market_data.py` | Live data fetching, liquidity, FVG, OB, confluence |
| `ai_analysis.py` | 17-phase AI/deterministic analysis pipeline |
| `trade_setup_engine.py` | Live deterministic strategy evaluator |
| `backtester.py` | Historical simulation engine |
| `analytics.py` | Win rate, PF, SQN, drawdown calculations |
| `mt5_sync.py` | MetaTrader 5 local bridge |
| `capital_sync.py` | Capital.com REST API bridge |
| `alerts.py` | Price alert daemon |

### Strategy Framework (`strategies/`)
| File | Purpose |
|------|---------|
| `base.py` | `BaseStrategy` abstract class — unified schema |
| `__init__.py` | Registry: `get_strategy()`, `get_all_strategy_names()` |
| `smc_utils.py` | Vectorized SMC: swings, FVG, sessions, PDH/PDL, Asian range |
| `ict_2022_model.py` | ICT 2022: SSL/BSL Sweep → MSS → FVG retracement |
| `liquidity_sweep.py` | Liquidity Sweep Reversal (immediate sweep entry) |
| `trend_continuation.py` | EMA crossover continuation |
| `mean_reversion.py` | RSI extreme reversal |

---

## 3. Strategy Framework — Critical Design Decisions

### Unified Execution Model
Both `trade_setup_engine.py` (live) and `backtester.py` (historical) call `strategy.analyze(df, current_index, context)` from the same registry. Zero duplicated logic.

### BaseStrategy Output Schema (Phase 6 — current)
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
    "liquidity_type": str,   # e.g. "BSL_PDH", "SSL_ASIAN", "SWING_LOW"
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
- **Column normalization**: All OHLC normalized to Title Case at entry (handles MT5 lowercase + yfinance Title Case)
- **Liquidity sweep priority**: PDH/PDL > Asian Range > Fractal Swings. Returns `type` field.

### Backtester Execution
- `MARKET`: fill at next bar Open + slippage
- `LIMIT`: fill when Low/High touches `ideal_entry`, gap-fill at Open if price gaps through
- Expiry: uses `setup['expiration_bars']`, defaults to 10
- Do NOT `df.dropna()` after SMC features — NaN is intentional for non-FVG bars

---

## 4. Known Bugs Fixed (Do Not Reintroduce)

| Bug | Fix |
|-----|-----|
| `KeyError: 'High'` on live data | `smc_utils.py` normalizes OHLC column names at entry with `col.capitalize()` |
| `TypeError: 'Timestamp' cannot be integer` | Use `df.index.get_loc(last_fvg_idx)` for `iloc` in `ict_2022_model.py` |
| `TradeSetupEngine unexpected kwarg 'strategy_name'` | Stale `.pyc` — clear `__pycache__` + `strategies/__pycache__` |
| `df.dropna()` wiping df after SMC features | Changed to `dropna(subset=['Open','High','Low','Close'])` |
| AI analysis running on every Streamlit rerun | Gated behind `▶ RUN ENGINE` button with `st.session_state` cache |
| Orphaned Streamlit process on port 8501 | `Get-Process python | Stop-Process -Force` then restart |

---

## 5. UI Tab Structure (app.py)

| Tab | Key Feature |
|-----|-------------|
| Analytics & Overview | Account metrics, equity curve, position table |
| Trading Workspace | Live chart, drawing tools, order execution panel |
| AI Market Context | `▶ RUN ENGINE` button → runs selected strategy on live data, caches result in session_state |
| Trade Journal | Per-trade journal with screenshots, setup tags, ratings |
| Price Alerts | Threshold alert management |
| Sandbox | Strategy selection, parameters, OOS backtest, equity curve |

**Important**: AI Market Context tab runs analysis ONLY on button press — not on every page load. Result cached by `AI_CACHE_KEY = f"ai_data_{symbol}_{tf}_{strategy}"`.

---

## 6. AI Analysis Pipeline (17 Phases)

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

## 7. Audit Results (30 Aug 2026)

| Component | Status |
|-----------|--------|
| Session detection (Asia/London/NY) | ✅ IMPLEMENTED |
| PDH / PDL | ✅ IMPLEMENTED |
| Asian Range High/Low | ✅ IMPLEMENTED (look-ahead safe) |
| Previous Week High/Low | ❌ NOT YET |
| Equal Highs/Lows detection | ❌ NOT YET |
| Look-ahead bias (swings + FVGs) | ✅ PASS (synthetic tests) |
| MTF strategy inputs | ❌ NOT YET (single-TF only) |
| Displacement validation | ❌ NOT YET (FVG assumed = displacement) |
| ICT SL beyond sweep low | ✅ IMPLEMENTED |
| LIMIT execution model + gap-fill | ✅ IMPLEMENTED |
| Live/backtest parity | ✅ VERIFIED |

---

## 8. Defaults

- **Default symbol**: USDJPY (XAUUSD secondary)
- **Default timeframe**: 15m
- **Default strategy**: ICT 2022 Model
- **Default risk per trade**: 1%
- **Data source priority**: MT5 → Binance (crypto) → Yahoo Finance

---

## 9. Next Development Priorities

1. Equal Highs/Lows detection in `smc_utils.py`
2. Previous Week High/Low in `smc_utils.py`
3. MTF strategy inputs — inject last completed higher-TF candle into `BaseStrategy.analyze()`
4. Displacement validation — verify impulsive move size vs ATR
5. Walk-forward / Monte Carlo in backtester
6. WebHook automation endpoints

---

## 10. How to Run

```powershell
# Start
cd C:\Users\Asus\Desktop\Trade_Logger
python -m streamlit run app.py

# Stop all Python processes
Get-Process python | Stop-Process -Force
```

---

## 11. Database Schema

| Table | Key Columns |
|-------|-------------|
| `closed_trades` | `trade_id`, `account_id`, `symbol`, `direction`, `volume`, `entry_price`, `exit_price`, `net_profit`, `entry_time`, `exit_time`, `setup_tag` |
| `open_positions` | `position_id`, `account_id`, `symbol`, `direction`, `volume`, `entry_price`, `sl`, `tp`, `floating_pnl` |
| `price_alerts` | `alert_id`, `symbol`, `target_price`, `condition`, `is_active` |
| `trade_journal` | `trade_id`, `notes`, `strategy`, `rating`, `screenshot_path` |
| `chart_drawings` | `symbol`, `drawings_data` |

---

## 12. Design System Tokens

| Token | Value |
|-------|-------|
| Background | `#0a0e17` |
| Cards | `#0e131f` / `#131722` |
| Bullish / Highlight | `#00ffcc` |
| Bearish / Loss | `#ff5555` |
| Warning / Gold | `#f59e0b` |
| Growth / Secondary | `#bef264` |
| Font | Inter + monospace numbers |


---

## 1. Current Architecture
* **Unified Backend**: FastAPI (`server.py`) serving REST APIs, database queries, market data feeds, WebSockets (`/ws/live_ticks`) for millisecond stream, and static Flutter Web assets.
* **Database Layer**: `database.py` with multi-tenant account isolation, supporting local SQLite (`trades.db`) and cloud PostgreSQL (`DATABASE_URL`).
* **Broker Adapters**:
  - `capital_sync.py`: Capital.com REST API v1 session authentication, trade fetching, order execution, position closing.
  - `mt5_sync.py`: Local Windows MetaTrader 5 C-extension bridge, deal reconstruction, balance fetching, order execution.
* **Analytics Engine**: `analytics.py` providing deterministic financial metrics (Win Rate, Profit Factor, Expectancy, SQN, Max DD, Long/Short performance).
* **AI Analysis Pipeline**: `ai_analysis.py` synthesizing deterministic indicators into structured market context with zero hallucination.
  - Phase 2: ML Engine 3-class deterministic edges.
  - Phase 3: Data Quality normalisation rules.
  - Phase 4: Multi-Timeframe Alignment math.
  - Phase 5: Deterministic Volatility Regimes (ADX).
  - Phase 6: Volume Profile (POC/VAH/VAL) & Session VWAP using Tick Volume.
  - Phase 7: Deterministic Market Structure (BOS/MSS & Swings).
  - Phase 8: Strict Liquidity Engine Audit (Price-relative BSL/SSL Geometry).
  - Phase 9: Fair Value Gaps (FVG) Mitigation Engine (Tested vs Untested).
  - Phase 10: Institutional Order Blocks (Unmitigated OB Detection).
  - Phase 11: Session Engine (Asian Range High/Low Mapping).
  - Phase 12: Macro/News Risk Engine (Implementation pipeline complete; uses deterministic mock).
  - Phase 13: Commitment of Traders (COT) Engine (Implementation pipeline complete; uses deterministic mock).
  - Phase 14: Cross-Asset Correlation Engine (Implementation pipeline complete; checks DXY vs Base Pair).
  - Phase 15: Confluence Engine (Deterministic AI Override - Weighs MTF/Macro/Technical factors for Bias).
  - Phase 16: Scenario Engine (Deterministic AI Override - Computes BSL/SSL targets and OB invalidation).
  - Phase 17: Final Validation Engine (Sanity checks macro risk and session timing).
* **AI Architecture Status**: FULLY COMPLETE. The dual-engine pipeline is completely built out and handles 17 phases of technical and fundamental synthesis.
* **Charting Engine**: `tradingview_widget.py` powered by Lightweight Charts 4.1.1 with precision `(time, price)` coordinate projection and SQLite drawing persistence.
* **User Interfaces**:
  - Desktop Terminal: Streamlit `app.py` (Multi-pane Trading Workspace, Analytics & Overview, AI Market Context, Trade Journal, Alerts).
  - Mobile & Web: Flutter 3 `trade_logger_app/`.

---

## 2. Working Features Status
* **Capital.com Account & Trade Sync**: `VERIFIED`
* **MT5 Local IPC Sync**: `VERIFIED`
* **Multi-Broker Account Separation**: `VERIFIED`
* **Unified Multi-Pane Trading Workspace**: `VERIFIED`
* **Coordinate-Locked Chart Drawing Tools**: `VERIFIED`
* **Pre-Trade Risk Management & Validation**: `VERIFIED`
* **Position Closure (MT5 & Capital.com)**: `VERIFIED`
* **Deterministic Analytics Calculations**: `VERIFIED`
* **Structured AI Market Context Engine**: `VERIFIED`
* **Persistent SQLite Drawing Storage**: `VERIFIED`
* **Threshold Price Alerts Daemon**: `VERIFIED`

---

## 3. Database Schema Summary
* `closed_trades`: `trade_id`, `account_id`, `symbol`, `direction`, `volume`, `entry_price`, `exit_price`, `commission`, `swap`, `gross_profit`, `net_profit`, `entry_time`, `exit_time`, `duration_minutes`, `setup_tag`.
* `raw_deals`: `deal_id`, `account_id`, `symbol`, `type`, `volume`, `price`, `commission`, `swap`, `profit`, `timestamp`, `position_id`.
* `open_positions`: `position_id`, `account_id`, `symbol`, `direction`, `volume`, `entry_price`, `current_price`, `sl`, `tp`, `floating_pnl`, `swap`, `open_time`, `updated_at`.
* `price_alerts`: `alert_id`, `symbol`, `target_price`, `condition`, `is_active`, `created_at`, `triggered_at`, `notes`.
* `trade_journal`: `trade_id`, `notes`, `strategy`, `rating`, `screenshot_path`, `updated_at`.
* `app_settings`: `key`, `value`.
* `chart_drawings`: `symbol`, `drawings_data`, `updated_at`.

---

## 4. Design System Tokens
* **Background Primary**: `#0a0e17`
* **Card & Sidebar Background**: `#0e131f` / `#131722`
* **Borders**: `rgba(255, 255, 255, 0.08)` / `rgba(0, 255, 204, 0.25)`
* **Semantic Cyan (Bullish / Highlight)**: `#00ffcc`
* **Semantic Lime (Growth / Secondary)**: `#bef264`
* **Semantic Red (Bearish / Loss)**: `#ff5555`
* **Semantic Gold (Warning / Fibonacci)**: `#f59e0b`
* **Typography**: Clean, high-density financial typography using `Inter` and monospace numbers.

---

* **Multi-Timeframe Strategy Backtesting Engine**: `VERIFIED` (Phase 2 Hardened: UTC Standardized, Instrument Sizing Modeled, OOS Split Available, Fixed Spread Modeled)

---

## 5. Next Priorities & Evolution
1. Advanced Research Engine (Walk-Forward Analysis Rolling, Monte Carlo).
2. WebHook trading automation payload endpoints.
3. Discord Integration (Paused/Deferred by user).
