"""Throwaway: wipe all multi-user accounts + their sessions so W10 sign-up can
be re-tested from scratch. Safe pre-launch (no real accounts exist yet).
Run:  python _reset_users.py     then delete this file.
"""
import database

conn = database.get_connection()
cur = conn.cursor()
try:
    cur.execute("DELETE FROM sessions WHERE user_id <> 'local'")
    sessions = cur.rowcount or 0
except Exception:
    conn.rollback()
    sessions = 0
try:
    cur.execute("DELETE FROM users")
    users = cur.rowcount or 0
except Exception:
    conn.rollback()
    users = 0
conn.commit()
conn.close()
print(f"deleted {users} account(s) and {sessions} session(s). Sign up fresh now.")
