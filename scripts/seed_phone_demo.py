# -*- coding: utf-8 -*-
"""
Creates ONE separate demo login with fake trades, positions, an alert and notes,
so the phone / desktop / web apps can be tried, shown or tested without touching
a real account.

  - Adds a brand-new user (DEMO_EMAIL) and rows that carry that user's id. It never
    reads, changes or deletes another user's data.
  - The demo user is not the owner, so "Sync now" / Auto-sync cannot reach the
    real broker credentials (it has no broker connection at all).
  - Writes to whatever database `database.py` resolves to (DATABASE_URL). On this
    machine that is the SAME Postgres the live site uses, so a real run needs --yes.

Usage:
    python scripts/seed_phone_demo.py --yes           # create the login + seed (idempotent; prints the password once)
    python scripts/seed_phone_demo.py --yes --reseed  # keep the login, replace its data with a fresh set
    python scripts/seed_phone_demo.py --yes --wipe    # delete the demo login and everything it owns
"""
from __future__ import annotations

import argparse
import os
import random
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Must be set before importing the app modules: lets create_account skip the invite list for THIS process only.
os.environ["TL_SIGNUP_OPEN"] = "1"
os.environ["TL_PUSH_ENABLED"] = "0"  # a seed run never pushes to anyone's phone

import database  # noqa: E402
import tenant  # noqa: E402
from api import identity  # noqa: E402

DEMO_EMAIL = "phone.demo@example.com"
DEMO_NAME = "Phone Demo"
ACCOUNTS = ("DEMO_MAIN", "DEMO_SECOND")


def _target() -> str:
    url = database.get_db_url() or ""
    if not url:
        return "local sqlite file"
    host = url.split("@")[-1].split("/")[0].split("?")[0]
    return f"Postgres @ {host}"


def _user_id() -> str | None:
    identity.ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = "%s" if database.is_postgres() else "?"
        cur.execute(f"SELECT id FROM users WHERE lower(email) = {ph}", (DEMO_EMAIL,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _tables_with_user_id(conn) -> list[str]:
    cur = conn.cursor()
    if database.is_postgres():
        cur.execute(
            "SELECT DISTINCT table_name FROM information_schema.columns "
            "WHERE column_name = 'user_id' AND table_schema = 'public'"
        )
        return [r[0] for r in cur.fetchall()]
    cur.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    out = []
    for (name,) in cur.fetchall():
        cur.execute(f'PRAGMA table_info("{name}")')
        if any(c[1] == "user_id" for c in cur.fetchall()):
            out.append(name)
    return out


def _delete_owned_rows(uid: str, and_user: bool) -> dict[str, int]:
    conn = database.get_connection()
    counts: dict[str, int] = {}
    try:
        cur = conn.cursor()
        ph = "%s" if database.is_postgres() else "?"
        for table in _tables_with_user_id(conn):
            if table == "users":
                continue
            cur.execute(f'DELETE FROM "{table}" WHERE user_id = {ph}', (uid,))
            counts[table] = cur.rowcount or 0
        if and_user:
            cur.execute(f"DELETE FROM users WHERE id = {ph}", (uid,))
            counts["users"] = cur.rowcount or 0
        conn.commit()
    finally:
        conn.close()
    database.invalidate_db_cache()
    return {k: v for k, v in counts.items() if v}


def _seed(uid: str) -> None:
    rng = random.Random(7)
    now = datetime.now(timezone.utc)
    symbols = [("US500", 6500.0), ("XAUUSD", 3900.0), ("EURUSD", 1.08), ("GBPUSD", 1.27)]
    tags = ["BREAKOUT", "ORDER BLOCK / FVG", "NEWS SCALP", None]
    main, second = ACCOUNTS
    with tenant.use(uid):
        n = 0
        for days_ago in range(50, -1, -1):
            if rng.random() < 0.35 and days_ago not in (0, 1):
                continue
            for _ in range(rng.choice([1, 1, 2, 3])):
                sym, px = rng.choice(symbols)
                win = rng.random() < 0.55
                gross = round(rng.uniform(8, 60) if win else -rng.uniform(6, 45), 2)
                exit_t = now - timedelta(days=days_ago, hours=rng.uniform(0.2, 10))
                entry_t = exit_t - timedelta(minutes=rng.randint(4, 240))
                database.add_manual_trade({
                    "account_id": main, "symbol": sym, "direction": rng.choice(["BUY", "SELL"]),
                    "volume": rng.choice([0.1, 0.5, 0.85]), "entry_price": px,
                    "exit_price": round(px * (1 + gross / 10000), 5), "commission": -1.0, "swap": 0.0,
                    "gross_profit": gross, "entry_time": entry_t.isoformat(), "exit_time": exit_t.isoformat(),
                    "setup_tag": rng.choice(tags), "notes": "demo trade" if rng.random() < 0.3 else None,
                })
                n += 1
        for i in range(6):
            exit_t = now - timedelta(days=i * 3 + 2)
            database.add_manual_trade({
                "account_id": second, "symbol": "EURUSD", "direction": "BUY", "volume": 0.05, "entry_price": 1.08,
                "exit_price": 1.081, "commission": 0.0, "swap": 0.0, "gross_profit": rng.choice([4.5, -3.2, 7.1]),
                "entry_time": (exit_t - timedelta(hours=1)).isoformat(), "exit_time": exit_t.isoformat(),
                "setup_tag": "BREAKOUT", "notes": None,
            })
            n += 1
        open_at = (now - timedelta(minutes=12)).strftime("%Y-%m-%dT%H:%M:%S")
        database.save_open_positions(main, [
            {"position_id": "DEMO_1001", "account_id": main, "symbol": "US500", "direction": "BUY", "volume": 0.5,
             "entry_price": 6500.25, "current_price": 6510.5, "sl": 6480.0, "tp": 6540.0, "floating_pnl": 5.12,
             "swap": 0.0, "open_time": open_at, "updated_at": now.isoformat()},
            {"position_id": "DEMO_1002", "account_id": main, "symbol": "XAUUSD", "direction": "SELL", "volume": 0.1,
             "entry_price": 3905.0, "current_price": 3911.0, "sl": None, "tp": None, "floating_pnl": -6.0,
             "swap": 0.0, "open_time": open_at, "updated_at": now.isoformat()},
        ])
        try:
            database.create_price_alert("XAUUSD", 4000, "ABOVE", notes="demo alert")
        except Exception as exc:  # noqa: BLE001 - e.g. the live price_alerts table has no id default yet
            print(f"(skipped the demo price alert: {type(exc).__name__})")
        database.create_journal_entry(f"demo-idea-{uid[:8]}", "idea", "XAUUSD", "Gold pullback idea",
                                      "Waiting for a sweep of the Asian low.", ["gold"])
        database.create_journal_entry(f"demo-plan-{uid[:8]}", "plan", "EURUSD", "EURUSD plan",
                                      "Entry 1.0800 stop 1.0750", ["plan"])
    print(f"seeded {n} closed trades, 2 open positions, 2 notes")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="really write to the database shown above")
    ap.add_argument("--reseed", action="store_true", help="replace the demo user's data with a fresh set")
    ap.add_argument("--wipe", action="store_true", help="delete the demo login and everything it owns")
    args = ap.parse_args()

    print(f"Target database: {_target()}")
    if not args.yes:
        print("Dry run - nothing written. Add --yes to go ahead.")
        return 0

    uid = _user_id()
    if args.wipe:
        if not uid:
            print("No demo login exists - nothing to remove.")
            return 0
        print("Removed:", _delete_owned_rows(uid, and_user=True))
        return 0

    password = None
    if not uid:
        password = secrets.token_urlsafe(9)
        user = identity.create_account(DEMO_EMAIL, password, DEMO_NAME, ip="")
        uid = user["id"]
        print(f"created login {DEMO_EMAIL}")
        # shown immediately, before anything else can fail
        print("\n  Email:    " + DEMO_EMAIL)
        print("  Password: " + password + "   (shown once - it is not stored anywhere readable)\n")
    elif args.reseed:
        _delete_owned_rows(uid, and_user=False)
    else:
        print(f"Demo login {DEMO_EMAIL} already exists - not touching it (use --reseed to refresh its data).")
        return 0

    _seed(uid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
