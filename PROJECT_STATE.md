# PROJECT STATE & ARCHITECTURAL RECORD
**Trading Super App — Living System Memory**
*Updated: August 2026*

---

## 1. Current Architecture
* **Unified Backend**: FastAPI (`server.py`) serving REST APIs, database queries, market data feeds, and static Flutter Web assets.
* **Database Layer**: `database.py` with multi-tenant account isolation, supporting local SQLite (`trades.db`) and cloud PostgreSQL (`DATABASE_URL`).
* **Broker Adapters**:
  - `capital_sync.py`: Capital.com REST API v1 session authentication, trade fetching, order execution, position closing.
  - `mt5_sync.py`: Local Windows MetaTrader 5 C-extension bridge, deal reconstruction, balance fetching, order execution.
* **Analytics Engine**: `analytics.py` providing deterministic financial metrics (Win Rate, Profit Factor, Expectancy, SQN, Max DD, Long/Short performance).
* **AI Analysis Pipeline**: `ai_analysis.py` synthesizing deterministic indicators into structured market context with zero hallucination.
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
1. Real-time WebSocket streaming for millisecond tick updates.
2. Webhook alert triggers to Telegram / Discord.
3. Multi-timeframe strategy backtesting sandbox.
