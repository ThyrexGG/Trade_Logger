import os
import sqlite3
import pandas as pd
from dotenv import load_dotenv

# MetaTrader 5 / Capital.com Database Handler
# Supports PostgreSQL (Supabase / Cloud) with graceful SQLite fallback

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

def get_db_url():
    # Check environment variable first
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url.strip('"\'')
        
    # Check Streamlit Cloud secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"]).strip('"\'')
    except Exception:
        pass
        
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
                setup_tag TEXT DEFAULT NULL
            )
        """)
    
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

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
