"""Clears all MT5 raw deals and closed trades from the DB so a fresh sync can rebuild them correctly."""
import sqlite3

conn = sqlite3.connect('trades.db')
cur = conn.cursor()

# Delete all MT5 data (account_id starts with MT5_)
cur.execute("DELETE FROM raw_deals WHERE account_id LIKE 'MT5_%'")
raw_deleted = cur.rowcount

cur.execute("DELETE FROM closed_trades WHERE account_id LIKE 'MT5_%'")
trades_deleted = cur.rowcount

conn.commit()
conn.close()

print(f"Cleared {raw_deleted} MT5 raw deals and {trades_deleted} MT5 closed trades.")
print("Now run: python mt5_sync.py   (or click Sync MT5 in the app)")
