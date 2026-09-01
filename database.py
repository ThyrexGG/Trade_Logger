import os
import time
import sqlite3
from datetime import datetime, timezone
import pandas as pd
from dotenv import load_dotenv

# MetaTrader 5 / Capital.com Database Handler
# Supports PostgreSQL (Supabase / Cloud) with graceful SQLite fallback

_DB_CACHE = {}

def invalidate_db_cache(prefix=None):
    if prefix is None:
        _DB_CACHE.clear()
    else:
        keys_to_del = [k for k in _DB_CACHE if k.startswith(prefix)]
        for k in keys_to_del:
            _DB_CACHE.pop(k, None)

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

def get_db_url():
    # 0. Check for local SQLite / Testing override
    if os.getenv("USE_LOCAL_SQLITE") == "1" or os.getenv("PYTEST_CURRENT_TEST"):
        return None

    # 1. Check Streamlit Cloud secrets first
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
            url = str(st.secrets["DATABASE_URL"]).strip('"\' \n\r\t')
            if url:
                return url
    except Exception:
        pass

    # 2. Check environment variable
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url.strip('"\' \n\r\t')
        
    return None

def is_postgres():
    return bool(get_db_url())

def get_sql_placeholder(conn=None):
    """
    Returns '%s' for PostgreSQL connections and '?' for SQLite connections.
    Foolproof across connection types and execution contexts.
    """
    if conn is not None:
        if isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3"):
            return "?"
        return "%s"
    return "%s" if is_postgres() else "?"

def get_connection():
    db_url = get_db_url()
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url)
    else:
        db_file = os.path.join(os.path.dirname(__file__), "trades.db")
        conn = sqlite3.connect(db_file, timeout=60.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=60000;")
        except Exception:
            pass
        return conn

def init_db():
    """Initializes the database and creates the necessary tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        # PostgreSQL Schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_deals (
                deal_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                type TEXT NOT NULL,
                volume DOUBLE PRECISION NOT NULL,
                price DOUBLE PRECISION NOT NULL,
                commission DOUBLE PRECISION DEFAULT 0,
                swap DOUBLE PRECISION DEFAULT 0,
                profit DOUBLE PRECISION DEFAULT 0,
                timestamp BIGINT NOT NULL,
                position_id TEXT NOT NULL
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS closed_trades (
                trade_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                volume DOUBLE PRECISION NOT NULL,
                entry_price DOUBLE PRECISION NOT NULL,
                exit_price DOUBLE PRECISION NOT NULL,
                commission DOUBLE PRECISION DEFAULT 0,
                swap DOUBLE PRECISION DEFAULT 0,
                gross_profit DOUBLE PRECISION DEFAULT 0,
                net_profit DOUBLE PRECISION DEFAULT 0,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                duration_minutes DOUBLE PRECISION DEFAULT 0,
                setup_tag TEXT DEFAULT NULL
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS open_positions (
                position_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                volume DOUBLE PRECISION NOT NULL,
                entry_price DOUBLE PRECISION NOT NULL,
                current_price DOUBLE PRECISION NOT NULL,
                sl DOUBLE PRECISION DEFAULT 0,
                tp DOUBLE PRECISION DEFAULT 0,
                floating_pnl DOUBLE PRECISION DEFAULT 0,
                swap DOUBLE PRECISION DEFAULT 0,
                open_time TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_metadata (
                account_id TEXT PRIMARY KEY,
                balance DOUBLE PRECISION NOT NULL,
                equity DOUBLE PRECISION NOT NULL,
                currency TEXT DEFAULT 'USD',
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_alerts (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                target_price DOUBLE PRECISION NOT NULL,
                condition TEXT NOT NULL,
                account_id TEXT DEFAULT 'ALL',
                status TEXT DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL,
                triggered_at TEXT,
                notes TEXT
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_audit_log (
                id SERIAL PRIMARY KEY,
                signal_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT,
                timeframe TEXT,
                direction TEXT,
                entry_price DOUBLE PRECISION,
                sl DOUBLE PRECISION,
                tp DOUBLE PRECISION,
                requested_risk DOUBLE PRECISION,
                actual_risk DOUBLE PRECISION,
                calculated_size DOUBLE PRECISION,
                final_size DOUBLE PRECISION,
                broker TEXT,
                validation_result TEXT,
                risk_result TEXT,
                execution_result TEXT,
                broker_order_id TEXT,
                execution_price DOUBLE PRECISION,
                error_msg TEXT,
                reject_reason TEXT
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_orders (
                execution_id TEXT PRIMARY KEY,
                signal_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                requested_quantity DOUBLE PRECISION,
                requested_entry DOUBLE PRECISION,
                stop_loss DOUBLE PRECISION,
                take_profit DOUBLE PRECISION,
                broker TEXT NOT NULL,
                mode TEXT NOT NULL,
                state TEXT NOT NULL,
                broker_order_id TEXT,
                broker_position_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                submitted_at TEXT,
                filled_at TEXT,
                unknown_at TEXT,
                resolved_at TEXT,
                last_error TEXT,
                reject_reason TEXT,
                reconciliation_status TEXT,
                signal_payload TEXT,
                execution_latency_ms DOUBLE PRECISION
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS received_signals (
                signal_id TEXT PRIMARY KEY,
                received_at TEXT NOT NULL,
                status TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                broker TEXT NOT NULL,
                order_id TEXT
            );
        """)
        
        # Add migration columns for execution_orders in Postgres safely
        try:
            cursor.execute("ALTER TABLE execution_orders ADD COLUMN IF NOT EXISTS updated_at TEXT;")
            cursor.execute("ALTER TABLE execution_orders ADD COLUMN IF NOT EXISTS filled_at TEXT;")
            cursor.execute("ALTER TABLE execution_orders ADD COLUMN IF NOT EXISTS unknown_at TEXT;")
            cursor.execute("ALTER TABLE execution_orders ADD COLUMN IF NOT EXISTS reject_reason TEXT;")
            cursor.execute("ALTER TABLE execution_orders ADD COLUMN IF NOT EXISTS reconciliation_status TEXT;")
            cursor.execute("ALTER TABLE execution_orders ADD COLUMN IF NOT EXISTS signal_payload TEXT;")
            cursor.execute("ALTER TABLE execution_orders ADD COLUMN IF NOT EXISTS execution_latency_ms DOUBLE PRECISION;")
        except Exception:
            pass

        # Add migration columns for closed_trades in Postgres safely
        try:
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN IF NOT EXISTS chart_snapshot_url TEXT;")
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN IF NOT EXISTS notes TEXT;")
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN IF NOT EXISTS rating INTEGER DEFAULT 0;")
        except Exception:
            pass
        # Add migration columns for received_signals safely
        try:
            cursor.execute("ALTER TABLE received_signals ADD COLUMN IF NOT EXISTS strategy TEXT DEFAULT 'Manual';")
            cursor.execute("ALTER TABLE received_signals ADD COLUMN IF NOT EXISTS timeframe TEXT DEFAULT 'Unknown';")
            cursor.execute("ALTER TABLE received_signals ADD COLUMN IF NOT EXISTS setup_type TEXT DEFAULT 'Unknown';")
            cursor.execute("ALTER TABLE received_signals ADD COLUMN IF NOT EXISTS session TEXT DEFAULT 'Unknown';")
            cursor.execute("ALTER TABLE received_signals ADD COLUMN IF NOT EXISTS htf_bias TEXT DEFAULT 'Unknown';")
            cursor.execute("ALTER TABLE received_signals ADD COLUMN IF NOT EXISTS confluence_score DOUBLE PRECISION DEFAULT 0;")
            cursor.execute("ALTER TABLE received_signals ADD COLUMN IF NOT EXISTS signal_outcome TEXT DEFAULT 'NOT_TRIGGERED';")
        except Exception:
            pass

        # Correlation Matrix
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS correlation_matrix (
                symbol_1 TEXT NOT NULL,
                symbol_2 TEXT NOT NULL,
                time_window INTEGER NOT NULL,
                correlation DOUBLE PRECISION NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (symbol_1, symbol_2, time_window)
            );
        """)
    else:
        # SQLite Schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_deals (
                deal_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                type TEXT NOT NULL,
                volume REAL NOT NULL,
                price REAL NOT NULL,
                commission REAL DEFAULT 0,
                swap REAL DEFAULT 0,
                profit REAL DEFAULT 0,
                timestamp INTEGER NOT NULL,
                position_id TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS closed_trades (
                trade_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                volume REAL NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                commission REAL DEFAULT 0,
                swap REAL DEFAULT 0,
                gross_profit REAL DEFAULT 0,
                net_profit REAL DEFAULT 0,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                duration_minutes REAL DEFAULT 0,
                setup_tag TEXT DEFAULT NULL,
                chart_snapshot_url TEXT DEFAULT NULL,
                notes TEXT DEFAULT NULL,
                rating INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS open_positions (
                position_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                volume REAL NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL NOT NULL,
                sl REAL DEFAULT 0,
                tp REAL DEFAULT 0,
                floating_pnl REAL DEFAULT 0,
                swap REAL DEFAULT 0,
                open_time TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_metadata (
                account_id TEXT PRIMARY KEY,
                balance REAL NOT NULL,
                equity REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                target_price REAL NOT NULL,
                condition TEXT NOT NULL,
                account_id TEXT DEFAULT 'ALL',
                status TEXT DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL,
                triggered_at TEXT DEFAULT NULL,
                notes TEXT DEFAULT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_orders (
                execution_id TEXT PRIMARY KEY,
                signal_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                requested_quantity REAL,
                requested_entry REAL,
                stop_loss REAL,
                take_profit REAL,
                broker TEXT NOT NULL,
                mode TEXT NOT NULL,
                state TEXT NOT NULL,
                broker_order_id TEXT,
                broker_position_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                submitted_at TEXT,
                filled_at TEXT,
                unknown_at TEXT,
                resolved_at TEXT,
                last_error TEXT,
                reject_reason TEXT,
                reconciliation_status TEXT,
                signal_payload TEXT,
                execution_latency_ms REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS received_signals (
                signal_id TEXT PRIMARY KEY,
                received_at TEXT NOT NULL,
                status TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                broker TEXT NOT NULL,
                order_id TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT,
                timeframe TEXT,
                direction TEXT,
                entry_price REAL,
                sl REAL,
                tp REAL,
                requested_risk REAL,
                actual_risk REAL,
                calculated_size REAL,
                final_size REAL,
                broker TEXT,
                validation_result TEXT,
                risk_result TEXT,
                execution_result TEXT,
                broker_order_id TEXT,
                execution_price REAL,
                error_msg TEXT,
                reject_reason TEXT
            )
        """)

        # Add migration columns for execution_orders and closed_trades safely
        for col_def in [
            ("execution_orders", "updated_at TEXT"),
            ("execution_orders", "filled_at TEXT"),
            ("execution_orders", "unknown_at TEXT"),
            ("execution_orders", "reject_reason TEXT"),
            ("execution_orders", "reconciliation_status TEXT"),
            ("execution_orders", "signal_payload TEXT"),
            ("execution_orders", "execution_latency_ms REAL"),
            ("closed_trades", "chart_snapshot_url TEXT DEFAULT NULL"),
            ("closed_trades", "notes TEXT DEFAULT NULL"),
            ("closed_trades", "rating INTEGER DEFAULT 0")
        ]:
            try:
                cursor.execute(f"ALTER TABLE {col_def[0]} ADD COLUMN {col_def[1]};")
            except Exception:
                pass
    
    conn.commit()
    conn.close()

def save_raw_deals(deals):
    """
    Saves a list of raw deals to the database.
    deals: List of dicts matching the raw_deals schema.
    """
    if not deals:
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        query = """
            INSERT INTO raw_deals 
            (deal_id, account_id, symbol, type, volume, price, commission, swap, profit, timestamp, position_id)
            VALUES 
            (%(deal_id)s, %(account_id)s, %(symbol)s, %(type)s, %(volume)s, %(price)s, %(commission)s, %(swap)s, %(profit)s, %(timestamp)s, %(position_id)s)
            ON CONFLICT (deal_id) DO NOTHING
        """
        cursor.executemany(query, deals)
    else:
        cursor.executemany("""
            INSERT OR IGNORE INTO raw_deals 
            (deal_id, account_id, symbol, type, volume, price, commission, swap, profit, timestamp, position_id)
            VALUES 
            (:deal_id, :account_id, :symbol, :type, :volume, :price, :commission, :swap, :profit, :timestamp, :position_id)
        """, deals)
        
    conn.commit()
    conn.close()

def save_closed_trades(trades):
    """
    Saves or updates processed trades in the database.
    trades: List of dicts matching the closed_trades schema.
    """
    if not trades:
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        query = """
            INSERT INTO closed_trades 
            (trade_id, account_id, symbol, direction, volume, entry_price, exit_price, 
             commission, swap, gross_profit, net_profit, entry_time, exit_time, duration_minutes, setup_tag)
            VALUES 
            (%(trade_id)s, %(account_id)s, %(symbol)s, %(direction)s, %(volume)s, %(entry_price)s, %(exit_price)s, 
             %(commission)s, %(swap)s, %(gross_profit)s, %(net_profit)s, %(entry_time)s, %(exit_time)s, %(duration_minutes)s, %(setup_tag)s)
            ON CONFLICT (trade_id) DO UPDATE SET
                account_id = EXCLUDED.account_id,
                symbol = EXCLUDED.symbol,
                direction = EXCLUDED.direction,
                volume = EXCLUDED.volume,
                entry_price = EXCLUDED.entry_price,
                exit_price = EXCLUDED.exit_price,
                commission = EXCLUDED.commission,
                swap = EXCLUDED.swap,
                gross_profit = EXCLUDED.gross_profit,
                net_profit = EXCLUDED.net_profit,
                entry_time = EXCLUDED.entry_time,
                exit_time = EXCLUDED.exit_time,
                duration_minutes = EXCLUDED.duration_minutes,
                setup_tag = COALESCE(EXCLUDED.setup_tag, closed_trades.setup_tag)
        """
        cursor.executemany(query, trades)
    else:
        cursor.executemany("""
            INSERT INTO closed_trades 
            (trade_id, account_id, symbol, direction, volume, entry_price, exit_price, 
             commission, swap, gross_profit, net_profit, entry_time, exit_time, duration_minutes, setup_tag)
            VALUES 
            (:trade_id, :account_id, :symbol, :direction, :volume, :entry_price, :exit_price, 
             :commission, :swap, :gross_profit, :net_profit, :entry_time, :exit_time, :duration_minutes, :setup_tag)
            ON CONFLICT(trade_id) DO UPDATE SET
                account_id = excluded.account_id,
                symbol = excluded.symbol,
                direction = excluded.direction,
                volume = excluded.volume,
                entry_price = excluded.entry_price,
                exit_price = excluded.exit_price,
                commission = excluded.commission,
                swap = excluded.swap,
                gross_profit = excluded.gross_profit,
                net_profit = excluded.net_profit,
                entry_time = excluded.entry_time,
                exit_time = excluded.exit_time,
                duration_minutes = excluded.duration_minutes,
                setup_tag = COALESCE(excluded.setup_tag, closed_trades.setup_tag)
        """, trades)
        
    conn.commit()
    conn.close()
    invalidate_db_cache("closed_trades")

def get_last_deal_timestamp(account_id):
    """Returns the timestamp of the latest logged deal for a given account to fetch incrementally."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("SELECT MAX(timestamp) FROM raw_deals WHERE account_id = %s", (account_id,))
    else:
        cursor.execute("SELECT MAX(timestamp) FROM raw_deals WHERE account_id = ?", (account_id,))
        
    row = cursor.fetchone()
    result = row[0] if row else None
    conn.close()
    return result if result else 0

def get_closed_trades(ttl_sec: float = 0.0):
    """Returns all closed trades as a pandas DataFrame."""
    if ttl_sec > 0:
        cache_key = "closed_trades"
        now_t = time.time()
        if cache_key in _DB_CACHE:
            cached_df, cached_time = _DB_CACHE[cache_key]
            if now_t - cached_time < ttl_sec and isinstance(cached_df, pd.DataFrame):
                return cached_df.copy()

    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM closed_trades ORDER BY exit_time DESC", conn)
    conn.close()
    if ttl_sec > 0:
        _DB_CACHE["closed_trades"] = (df, time.time())
    return df.copy()

def update_setup_tag(trade_id, setup_tag):
    """Updates the subjective setup tag for a specific trade."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("UPDATE closed_trades SET setup_tag = %s WHERE trade_id = %s", (setup_tag, trade_id))
    else:
        cursor.execute("UPDATE closed_trades SET setup_tag = ? WHERE trade_id = ?", (setup_tag, trade_id))
        
    conn.commit()
    conn.close()
    invalidate_db_cache("closed_trades")

def save_open_positions(account_id, positions):
    """Replaces current open positions for an account with the latest snapshot."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Clear previous open positions for this account
    if is_postgres():
        cursor.execute("DELETE FROM open_positions WHERE account_id = %s", (account_id,))
    else:
        cursor.execute("DELETE FROM open_positions WHERE account_id = ?", (account_id,))
        
    # 2. Insert active positions if any
    if positions:
        if is_postgres():
            query = """
                INSERT INTO open_positions 
                (position_id, account_id, symbol, direction, volume, entry_price, current_price, 
                 sl, tp, floating_pnl, swap, open_time, updated_at)
                VALUES 
                (%(position_id)s, %(account_id)s, %(symbol)s, %(direction)s, %(volume)s, 
                 %(entry_price)s, %(current_price)s, %(sl)s, %(tp)s, %(floating_pnl)s, 
                 %(swap)s, %(open_time)s, %(updated_at)s)
            """
            cursor.executemany(query, positions)
        else:
            cursor.executemany("""
                INSERT OR REPLACE INTO open_positions 
                (position_id, account_id, symbol, direction, volume, entry_price, current_price, 
                 sl, tp, floating_pnl, swap, open_time, updated_at)
                VALUES 
                (:position_id, :account_id, :symbol, :direction, :volume, :entry_price, :current_price, 
                 :sl, :tp, :floating_pnl, :swap, :open_time, :updated_at)
            """, positions)
            
    conn.commit()
    conn.close()
    invalidate_db_cache("open_positions")

def get_open_positions(account_id=None, ttl_sec: float = 0.0):
    """Returns currently open positions as a pandas DataFrame."""
    if ttl_sec > 0:
        cache_key = f"open_positions_{account_id}"
        now_t = time.time()
        if cache_key in _DB_CACHE:
            cached_df, cached_time = _DB_CACHE[cache_key]
            if now_t - cached_time < ttl_sec and isinstance(cached_df, pd.DataFrame):
                return cached_df.copy()

    conn = get_connection()
    if account_id and account_id != "ALL":
        if is_postgres():
            df = pd.read_sql_query("SELECT * FROM open_positions WHERE account_id = %s ORDER BY open_time DESC", conn, params=(account_id,))
        else:
            df = pd.read_sql_query("SELECT * FROM open_positions WHERE account_id = ? ORDER BY open_time DESC", conn, params=(account_id,))
    else:
        df = pd.read_sql_query("SELECT * FROM open_positions ORDER BY open_time DESC", conn)
    conn.close()
    if ttl_sec > 0:
        _DB_CACHE[f"open_positions_{account_id}"] = (df, time.time())
    return df.copy()

def save_account_balance(account_id, balance, equity, currency="USD"):
    """Saves official live broker balance and equity for an account."""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    if is_postgres():
        query = """
            INSERT INTO account_metadata (account_id, balance, equity, currency, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (account_id) DO UPDATE SET
                balance = EXCLUDED.balance,
                equity = EXCLUDED.equity,
                currency = EXCLUDED.currency,
                updated_at = EXCLUDED.updated_at
        """
        cursor.execute(query, (account_id, float(balance), float(equity), currency, now_iso))
    else:
        cursor.execute("""
            INSERT OR REPLACE INTO account_metadata (account_id, balance, equity, currency, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (account_id, float(balance), float(equity), currency, now_iso))
        
    conn.commit()
    conn.close()

def get_account_balances():
    """Returns a dict of {account_id: {'balance': float, 'equity': float, 'currency': str}} from database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT account_id, balance, equity, currency FROM account_metadata")
    rows = cursor.fetchall()
    conn.close()
    
    balances = {}
    for row in rows:
        balances[str(row[0])] = {
            "balance": float(row[1]),
            "equity": float(row[2]),
            "currency": str(row[3])
        }
    return balances

# ----------------- Price Alerts Management -----------------

def create_price_alert(symbol, target_price, condition, account_id="ALL", notes=""):
    """Creates a new price alert in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    if is_postgres():
        cursor.execute("""
            INSERT INTO price_alerts (symbol, target_price, condition, account_id, status, created_at, notes)
            VALUES (%s, %s, %s, %s, 'ACTIVE', %s, %s)
            RETURNING id
        """, (str(symbol).upper(), float(target_price), str(condition).upper(), account_id, now_iso, notes))
        alert_id = cursor.fetchone()[0]
    else:
        cursor.execute("""
            INSERT INTO price_alerts (symbol, target_price, condition, account_id, status, created_at, notes)
            VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?)
        """, (str(symbol).upper(), float(target_price), str(condition).upper(), account_id, now_iso, notes))
        alert_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return alert_id

def get_active_price_alerts():
    """Returns a list of all ACTIVE price alerts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, symbol, target_price, condition, account_id, notes, created_at FROM price_alerts WHERE status = 'ACTIVE'")
    rows = cursor.fetchall()
    conn.close()
    
    alerts = []
    for r in rows:
        alerts.append({
            "id": r[0],
            "symbol": str(r[1]).upper(),
            "target_price": float(r[2]),
            "condition": str(r[3]).upper(),
            "account_id": str(r[4]),
            "notes": str(r[5] or ""),
            "created_at": str(r[6])
        })
    return alerts

def get_all_price_alerts(limit=50):
    """Returns a pandas DataFrame of all price alerts (ACTIVE and TRIGGERED)."""
    conn = get_connection()
    if is_postgres():
        df = pd.read_sql_query("SELECT * FROM price_alerts ORDER BY id DESC LIMIT %s", conn, params=(limit,))
    else:
        df = pd.read_sql_query("SELECT * FROM price_alerts ORDER BY id DESC LIMIT ?", conn, params=(limit,))
    conn.close()
    return df

def mark_price_alert_triggered(alert_id):
    """Marks a price alert as TRIGGERED."""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    if is_postgres():
        cursor.execute("UPDATE price_alerts SET status = 'TRIGGERED', triggered_at = %s WHERE id = %s", (now_iso, int(alert_id)))
    else:
        cursor.execute("UPDATE price_alerts SET status = 'TRIGGERED', triggered_at = ? WHERE id = ?", (now_iso, int(alert_id)))
    conn.commit()
    conn.close()
    return True

def delete_price_alert(alert_id):
    """Deletes a price alert from database."""
    conn = get_connection()
    cursor = conn.cursor()
    if is_postgres():
        cursor.execute("DELETE FROM price_alerts WHERE id = %s", (int(alert_id),))
    else:
        cursor.execute("DELETE FROM price_alerts WHERE id = ?", (int(alert_id),))
    conn.commit()
    conn.close()
    return True

# ----------------- Trade Journal Snapshots & Notes -----------------

def update_trade_journal(trade_id, chart_snapshot_url=None, setup_tag=None, notes=None, rating=None):
    """Updates chart snapshot, setup category, notes, and rating for a closed trade."""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if chart_snapshot_url is not None:
        updates.append("chart_snapshot_url = %s" if is_postgres() else "chart_snapshot_url = ?")
        params.append(str(chart_snapshot_url))
    if setup_tag is not None:
        updates.append("setup_tag = %s" if is_postgres() else "setup_tag = ?")
        params.append(str(setup_tag))
    if notes is not None:
        updates.append("notes = %s" if is_postgres() else "notes = ?")
        params.append(str(notes))
    if rating is not None:
        updates.append("rating = %s" if is_postgres() else "rating = ?")
        params.append(int(rating))
        
    if not updates:
        conn.close()
        return False
        
    params.append(str(trade_id))
    query = f"UPDATE closed_trades SET {', '.join(updates)} WHERE trade_id = {'%s' if is_postgres() else '?'}"
    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()
    return True

# ----------------- Starred / Favorite Symbols -----------------

def get_favorite_symbols():
    """Returns a list of starred/favorite symbol names in uppercase."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS favorite_symbols (symbol TEXT PRIMARY KEY, created_at TEXT NOT NULL)")
        cursor.execute("SELECT symbol FROM favorite_symbols ORDER BY created_at ASC")
        rows = cursor.fetchall()
        conn.close()
        favs = [str(r[0]).upper() for r in rows]
        if not favs:
            # Default initial favorites
            return ["XAUUSD", "EURUSD", "US100"]
        return favs
    except Exception as e:
        print(f"Error fetching favorite symbols: {e}")
        return ["XAUUSD", "EURUSD", "US100"]

def toggle_favorite_symbol(symbol):
    """Toggles star/favorite status for a symbol."""
    sym = str(symbol).strip().upper()
    if not sym or sym == "CUSTOM":
        return False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS favorite_symbols (symbol TEXT PRIMARY KEY, created_at TEXT NOT NULL)")
        if is_postgres():
            cursor.execute("SELECT symbol FROM favorite_symbols WHERE symbol = %s", (sym,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute("DELETE FROM favorite_symbols WHERE symbol = %s", (sym,))
            else:
                cursor.execute("INSERT INTO favorite_symbols (symbol, created_at) VALUES (%s, %s)", (sym, datetime.now(timezone.utc).isoformat()))
        else:
            cursor.execute("SELECT symbol FROM favorite_symbols WHERE symbol = ?", (sym,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute("DELETE FROM favorite_symbols WHERE symbol = ?", (sym,))
            else:
                cursor.execute("INSERT INTO favorite_symbols (symbol, created_at) VALUES (?, ?)", (sym, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error toggling favorite symbol: {e}")
        return False

# ----------------- App Settings & Saved Chart Layouts -----------------

def get_setting(key, default=""):
    """Fetches a saved app setting by key."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        if is_postgres():
            cursor.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
        else:
            cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception as e:
        print(f"Error reading setting {key}: {e}")
        return default

def set_setting(key, value):
    """Saves or updates an app setting."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        val_str = str(value)
        if is_postgres():
            cursor.execute("""
                INSERT INTO app_settings (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (key, val_str))
        else:
            cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, val_str))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving setting {key}: {e}")
        return False

# ----------------- Super App Chart Drawings Database -----------------

def get_chart_drawings(symbol):
    """Fetches saved chart drawings JSON for a specific symbol."""
    sym = str(symbol).strip().upper()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chart_drawings (
                symbol TEXT PRIMARY KEY,
                drawings_data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        if is_postgres():
            cursor.execute("SELECT drawings_data FROM chart_drawings WHERE symbol = %s", (sym,))
        else:
            cursor.execute("SELECT drawings_data FROM chart_drawings WHERE symbol = ?", (sym,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else "[]"
    except Exception as e:
        print(f"Error reading drawings for {sym}: {e}")
        return "[]"

def save_chart_drawings(symbol, drawings_json):
    """Saves or updates chart drawings JSON for a specific symbol."""
    sym = str(symbol).strip().upper()
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chart_drawings (
                symbol TEXT PRIMARY KEY,
                drawings_data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        if is_postgres():
            cursor.execute("""
                INSERT INTO chart_drawings (symbol, drawings_data, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    drawings_data = EXCLUDED.drawings_data,
                    updated_at = EXCLUDED.updated_at
            """, (sym, str(drawings_json), now_str))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO chart_drawings (symbol, drawings_data, updated_at)
                VALUES (?, ?, ?)
            """, (sym, str(drawings_json), now_str))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving drawings for {sym}: {e}")
        return False

# ----------------- Execution Audit Log Database -----------------

def log_execution(log_data: dict):
    """Saves a structured record of an execution attempt."""
    conn = get_connection()
    cursor = conn.cursor()
    
    keys = ["signal_id", "timestamp", "symbol", "strategy", "timeframe", "direction", 
            "entry_price", "sl", "tp", "requested_risk", "actual_risk", "calculated_size", 
            "final_size", "broker", "validation_result", "risk_result", "execution_result", 
            "broker_order_id", "execution_price", "error_msg", "reject_reason"]
    
    for k in keys:
        if k not in log_data:
            log_data[k] = None
            
    cols = ", ".join(keys)
    if is_postgres():
        vals = ", ".join([f"%({k})s" for k in keys])
        cursor.execute(f"INSERT INTO execution_audit_log ({cols}) VALUES ({vals})", log_data)
    else:
        vals = ", ".join([f":{k}" for k in keys])
        cursor.execute(f"INSERT INTO execution_audit_log ({cols}) VALUES ({vals})", log_data)
        
    conn.commit()
    conn.close()

def get_recent_audit_logs(limit=50):
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT * FROM execution_audit_log ORDER BY id DESC LIMIT {limit}", conn)
    conn.close()
    return df.to_dict(orient="records")

# ----------------- Idempotency & Replay Protection -----------------

def has_signal(signal_id: str) -> bool:
    """Checks if a signal_id has already been processed to ensure idempotency."""
    if not signal_id:
        return False
    try:
        conn = get_connection()
        df = pd.read_sql_query(f"SELECT signal_id FROM received_signals WHERE signal_id = '{signal_id}'", conn)
        conn.close()
        return not df.empty
    except Exception:
        # In case of DB failure during idempotency check, default to False to fail closed later if needed,
        # but realistically we shouldn't block on just this check failing if the execution log works.
        # Actually, for safety, if we can't check idempotency, we should probably fail closed.
        raise RuntimeError("Database unavailable for idempotency check.")

def record_signal(signal_id: str, status: str, symbol: str, direction: str, broker: str, order_id: str = None,
                  strategy: str = "Manual", timeframe: str = "Unknown", setup_type: str = "Unknown",
                  session: str = "Unknown", htf_bias: str = "Unknown", confluence_score: float = 0.0,
                  signal_outcome: str = "NOT_TRIGGERED"):
    """Records a processed signal into the database."""
    if not signal_id:
        return
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if is_postgres():
            cursor.execute("""
                INSERT INTO received_signals (
                    signal_id, received_at, status, symbol, direction, broker, order_id,
                    strategy, timeframe, setup_type, session, htf_bias, confluence_score, signal_outcome
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (signal_id) DO UPDATE SET
                    signal_outcome = EXCLUDED.signal_outcome,
                    status = EXCLUDED.status,
                    order_id = EXCLUDED.order_id
            """, (signal_id, now_str, status, symbol, direction, broker, order_id, 
                  strategy, timeframe, setup_type, session, htf_bias, float(confluence_score), signal_outcome))
        else:
            cursor.execute("""
                INSERT INTO received_signals (
                    signal_id, received_at, status, symbol, direction, broker, order_id,
                    strategy, timeframe, setup_type, session, htf_bias, confluence_score, signal_outcome
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(signal_id) DO UPDATE SET
                    signal_outcome=excluded.signal_outcome,
                    status=excluded.status,
                    order_id=excluded.order_id
            """, (signal_id, now_str, status, symbol, direction, broker, order_id,
                  strategy, timeframe, setup_type, session, htf_bias, float(confluence_score), signal_outcome))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error recording signal {signal_id}: {e}")

def save_correlation(symbol_1: str, symbol_2: str, time_window: int, correlation: float):
    """Saves a correlation value between two symbols."""
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Always store alphabetically to prevent duplicates (e.g. A-B vs B-A)
        s1, s2 = sorted([symbol_1, symbol_2])
        
        if is_postgres():
            cursor.execute("""
                INSERT INTO correlation_matrix (symbol_1, symbol_2, time_window, correlation, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (symbol_1, symbol_2, time_window) DO UPDATE SET
                    correlation = EXCLUDED.correlation,
                    updated_at = EXCLUDED.updated_at
            """, (s1, s2, time_window, float(correlation), now_str))
        else:
            cursor.execute("""
                INSERT INTO correlation_matrix (symbol_1, symbol_2, time_window, correlation, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol_1, symbol_2, time_window) DO UPDATE SET
                    correlation=excluded.correlation,
                    updated_at=excluded.updated_at
            """, (s1, s2, time_window, float(correlation), now_str))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving correlation {symbol_1}-{symbol_2}: {e}")

def get_correlations(time_window: int = 20):
    """Returns a dictionary mapping (symbol_1, symbol_2) to their correlation value."""
    try:
        conn = get_connection()
        df = pd.read_sql_query(f"SELECT symbol_1, symbol_2, correlation FROM correlation_matrix WHERE time_window = {int(time_window)}", conn)
        conn.close()
        
        result = {}
        for _, row in df.iterrows():
            result[(row["symbol_1"], row["symbol_2"])] = float(row["correlation"])
            result[(row["symbol_2"], row["symbol_1"])] = float(row["correlation"])
        return result
    except Exception as e:
        print(f"Error reading correlations: {e}")
        return {}

def log_execution(log_data: dict):
    """Logs an execution attempt to execution_audit_log."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        
        sig_id = str(log_data.get("signal_id", "UNKNOWN"))
        ts = str(log_data.get("timestamp", now_str))
        sym = str(log_data.get("symbol", ""))
        strat = str(log_data.get("strategy", "Manual"))
        tf = str(log_data.get("timeframe", "Unknown"))
        direction = str(log_data.get("direction", log_data.get("side", "")))
        entry = float(log_data.get("entry_price", log_data.get("requested_entry", 0.0)))
        sl = float(log_data.get("sl", log_data.get("stop_loss", 0.0))) if log_data.get("sl") or log_data.get("stop_loss") else None
        tp = float(log_data.get("tp", log_data.get("take_profit", 0.0))) if log_data.get("tp") or log_data.get("take_profit") else None
        req_risk = float(log_data.get("requested_risk", 0.0))
        act_risk = float(log_data.get("actual_risk", 0.0))
        calc_sz = float(log_data.get("calculated_size", log_data.get("requested_quantity", log_data.get("volume", 0.0))))
        final_sz = float(log_data.get("final_size", calc_sz))
        broker = str(log_data.get("broker", "CAPITAL"))
        val_res = str(log_data.get("validation_result", "PASSED"))
        risk_res = str(log_data.get("risk_result", "APPROVED"))
        exec_res = str(log_data.get("execution_result", "FILLED"))
        b_oid = str(log_data.get("broker_order_id", "")) if log_data.get("broker_order_id") else None
        exec_px = float(log_data.get("execution_price", entry)) if log_data.get("execution_price") else None
        err = str(log_data.get("error_msg", "")) if log_data.get("error_msg") else None
        rej = str(log_data.get("reject_reason", "")) if log_data.get("reject_reason") else None

        if is_postgres():
            cursor.execute("""
                INSERT INTO execution_audit_log (
                    signal_id, timestamp, symbol, strategy, timeframe, direction,
                    entry_price, sl, tp, requested_risk, actual_risk, calculated_size, final_size,
                    broker, validation_result, risk_result, execution_result, broker_order_id,
                    execution_price, error_msg, reject_reason
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (sig_id, ts, sym, strat, tf, direction, entry, sl, tp, req_risk, act_risk, calc_sz, final_sz,
                  broker, val_res, risk_res, exec_res, b_oid, exec_px, err, rej))
        else:
            cursor.execute("""
                INSERT INTO execution_audit_log (
                    signal_id, timestamp, symbol, strategy, timeframe, direction,
                    entry_price, sl, tp, requested_risk, actual_risk, calculated_size, final_size,
                    broker, validation_result, risk_result, execution_result, broker_order_id,
                    execution_price, error_msg, reject_reason
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (sig_id, ts, sym, strat, tf, direction, entry, sl, tp, req_risk, act_risk, calc_sz, final_sz,
                  broker, val_res, risk_res, exec_res, b_oid, exec_px, err, rej))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging execution audit: {e}")

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with Price Alerts, Trade Journal, and Favorite Symbols.")


