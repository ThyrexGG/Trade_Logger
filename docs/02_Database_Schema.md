# TradeLogger Database Schema (`trades.db`)

The application uses SQLite3 as a local database. The initialization logic is handled in `database.py`. The database automatically builds the following core tables if they do not exist.

## 1. `closed_trades`
Stores historical, completed executions synced from brokers or manually entered.
- `id` (INTEGER PRIMARY KEY)
- `trade_id` (TEXT UNIQUE) - The broker's ticket/order ID.
- `symbol` (TEXT) - e.g., 'XAUUSD', 'NAS100'.
- `direction` (TEXT) - 'BUY' or 'SELL'.
- `entry_time` (TEXT) - ISO datetime string.
- `exit_time` (TEXT) - ISO datetime string.
- `entry_price` (REAL)
- `exit_price` (REAL)
- `volume` (REAL) - Lot size or quantity.
- `net_profit` (REAL) - Final PnL in USD.
- `setup_name` (TEXT) - User-assigned strategy tag.
- `notes` (TEXT) - User reflections on the trade.
- `chart_snapshot_url` (TEXT) - Local file path or base64 string to a saved chart image.
- `broker` (TEXT) - e.g., 'MT5' or 'CAPITAL.COM'.

## 2. `open_positions`
Tracks live positions currently active on the broker.
- `id` (INTEGER PRIMARY KEY)
- `position_id` (TEXT UNIQUE)
- `symbol` (TEXT)
- `direction` (TEXT)
- `volume` (REAL)
- `open_price` (REAL)
- `open_time` (TEXT)
- `sl` (REAL) - Stop Loss.
- `tp` (REAL) - Take Profit.
- `current_price` (REAL) - Last synced price.
- `unrealized_pnl` (REAL) - Floating PnL.
- `broker` (TEXT)

## 3. `account_metrics`
Snapshots of account equity and balance over time for dashboard charting.
- `id` (INTEGER PRIMARY KEY)
- `timestamp` (TEXT)
- `balance` (REAL)
- `equity` (REAL)
- `margin_free` (REAL)
- `broker` (TEXT)

## 4. `price_alerts`
User-defined price thresholds for notifications.
- `id` (INTEGER PRIMARY KEY)
- `symbol` (TEXT)
- `target_price` (REAL)
- `condition` (TEXT) - 'ABOVE' or 'BELOW'.
- `is_active` (INTEGER) - 1 (Active) or 0 (Triggered).
- `created_at` (TEXT)

## 5. `drawings`
Stores serialized JSON payloads of user annotations (trendlines, fibs, boxes) made in the Native TradingView chart.
- `id` (INTEGER PRIMARY KEY)
- `symbol` (TEXT UNIQUE)
- `payload` (TEXT) - A JSON string representing the coordinates of all shapes.
