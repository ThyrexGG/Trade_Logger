# PROJECT STATE & ARCHITECTURAL RECORD
**Trading Super App — Living System Memory**
*Updated: August 2026*

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

## 5. Next Priorities & Evolution
1. Multi-timeframe strategy backtesting sandbox.
2. WebHook trading automation payload endpoints.
