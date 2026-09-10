"""Throwaway: hand the single-user 'local' rows to the owner account.

This is what Alembic 0003 does, run directly — needed when 0003 was applied
before the owner signed up (so it was a no-op and won't re-run).

    python _reown_local.py            # uses TL_OWNER_EMAIL or the 'owner' role
    python _reown_local.py you@x.com  # or name the owner explicitly

Then delete this file.
"""
import os
import sys

import database

_TABLES = (
    "raw_deals", "closed_trades", "open_positions", "account_metadata",
    "price_alerts", "journal_entries", "journal_screenshots",
)

email = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("TL_OWNER_EMAIL", "")).strip().lower()

conn = database.get_connection()
cur = conn.cursor()
ph = database.get_sql_placeholder(conn)

owner_id = None
if email:
    cur.execute(f"SELECT id FROM users WHERE lower(email) = {ph}", (email,))
    row = cur.fetchone()
    owner_id = row[0] if row else None
if not owner_id:
    cur.execute("SELECT id, email FROM users WHERE role = 'owner' ORDER BY created_at LIMIT 1")
    row = cur.fetchone()
    if row:
        owner_id, email = row[0], row[1]

if not owner_id:
    conn.close()
    raise SystemExit("No owner account found. Sign up as the owner first.")

moved = 0
for t in _TABLES:
    try:
        cur.execute(f"UPDATE {t} SET user_id = {ph} WHERE user_id = 'local'", (owner_id,))
        moved += cur.rowcount or 0
    except Exception as exc:
        print(f"  {t}: skipped ({exc})")
        conn.rollback()
conn.commit()
conn.close()
print(f"re-owned {moved} row(s) to {owner_id}  ({email})")
