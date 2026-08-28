import os
import sqlite3
from datetime import datetime, timezone
import pandas as pd
from dotenv import load_dotenv

# MetaTrader 5 / Capital.com Database Handler
# Supports PostgreSQL (Supabase / Cloud) with graceful SQLite fallback

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

def get_db_url():
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

def get_connection():
    db_url = get_db_url()
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url)
    else:
        db_file = os.path.join(os.path.dirname(__file__), "trades.db")
        return sqlite3.connect(db_file)

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
        
        # Add migration columns for closed_trades in Postgres safely
        try:
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN IF NOT EXISTS chart_snapshot_url TEXT;")
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN IF NOT EXISTS notes TEXT;")
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN IF NOT EXISTS rating INTEGER DEFAULT 0;")
        except Exception:
            pass
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

        # Add migration columns for existing closed_trades SQLite table safely
        try:
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN chart_snapshot_url TEXT DEFAULT NULL;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN notes TEXT DEFAULT NULL;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE closed_trades ADD COLUMN rating INTEGER DEFAULT 0;")
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
            INSERT OR REPLACE INTO closed_trades 
            (trade_id, account_id, symbol, direction, volume, entry_price, exit_price, 
             commission, swap, gross_profit, net_profit, entry_time, exit_time, duration_minutes, setup_tag)
            VALUES 
            (:trade_id, :account_id, :symbol, :direction, :volume, :entry_price, :exit_price, 
             :commission, :swap, :gross_profit, :net_profit, :entry_time, :exit_time, :duration_minutes, :setup_tag)
        """, trades)
        
    conn.commit()
    conn.close()

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

def get_closed_trades():
    """Returns all closed trades as a pandas DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM closed_trades ORDER BY exit_time DESC", conn)
    conn.close()
    return df

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

def get_open_positions(account_id=None):
    """Returns currently open positions as a pandas DataFrame."""
    conn = get_connection()
    if account_id and account_id != "ALL":
        if is_postgres():
            df = pd.read_sql_query("SELECT * FROM open_positions WHERE account_id = %s ORDER BY open_time DESC", conn, params=(account_id,))
        else:
            df = pd.read_sql_query("SELECT * FROM open_positions WHERE account_id = ? ORDER BY open_time DESC", conn, params=(account_id,))
    else:
        df = pd.read_sql_query("SELECT * FROM open_positions ORDER BY open_time DESC", conn)
    conn.close()
    return df

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

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with Price Alerts and Trade Journal enhancements.")
