import sqlite3
import os
import pandas as pd

DB_FILE = os.path.join(os.path.dirname(__file__), "trades.db")

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    """Initializes the SQLite database and creates the necessary tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Raw deals table (to store exact executions)
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
    
    # 2. Reconstructed closed trades table
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
    cursor.execute("SELECT MAX(timestamp) FROM raw_deals WHERE account_id = ?", (account_id,))
    result = cursor.fetchone()[0]
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
    cursor.execute("UPDATE closed_trades SET setup_tag = ? WHERE trade_id = ?", (setup_tag, trade_id))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
