import sqlite3

conn = sqlite3.connect('trades.db')
cur = conn.cursor()

# Check for MT5 trades (account_id is NOT the Capital.com one)
cur.execute("SELECT * FROM closed_trades WHERE account_id != '304665047035106500'")
mt5_trades = cur.fetchall()
print(f"MT5 trades in DB: {len(mt5_trades)}")
for t in mt5_trades:
    print(t)

# Also check raw_deals for MT5
cur.execute("SELECT * FROM raw_deals WHERE account_id != '304665047035106500'")
mt5_raw = cur.fetchall()
print(f"\nMT5 raw deals in DB: {len(mt5_raw)}")
for t in mt5_raw:
    print(t)

conn.close()
