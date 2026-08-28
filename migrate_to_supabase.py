import sqlite3
import database

print("Initializing Supabase PostgreSQL database tables...")
database.init_db()

sqlite_conn = sqlite3.connect("trades.db")
sqlite_conn.row_factory = sqlite3.Row
cur = sqlite_conn.cursor()

# 1. Migrate raw_deals
cur.execute("SELECT * FROM raw_deals")
raw_rows = [dict(r) for r in cur.fetchall()]
print(f"Migrating {len(raw_rows)} raw deals from SQLite to Supabase...")
database.save_raw_deals(raw_rows)

# 2. Migrate closed_trades
cur.execute("SELECT * FROM closed_trades")
trades_rows = [dict(r) for r in cur.fetchall()]
print(f"Migrating {len(trades_rows)} closed trades from SQLite to Supabase...")
database.save_closed_trades(trades_rows)

sqlite_conn.close()

# Verify Supabase counts
df = database.get_closed_trades()
print(f"Verification: Successfully verified {len(df)} trades in Supabase PostgreSQL database!")
print(df[["trade_id", "account_id", "symbol", "direction", "net_profit"]].head(10))
