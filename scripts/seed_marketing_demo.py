# -*- coding: utf-8 -*-
"""
Seeds a fake-but-realistic "MARKETING-DEMO" trading account for screen
recording / marketing content — a populated journal, a positive equity
curve, sane win rate and profit factor, without touching any real trade.

Why this exists: recording the app with an empty account (or your real,
sparse local history) doesn't look like much. This inserts ~85 days of
plausible EURUSD/GBPUSD/USDJPY/XAUUSD trades under a clearly-fake
`account_id` ("MARKETING-DEMO") so Analytics / Journal / Command Center
have something to show.

Safety:
  - Only ever touches rows with account_id == "MARKETING-DEMO". Never reads,
    modifies or deletes anything else.
  - Seeded under a DEDICATED demo login (DEMO_LOGIN_EMAIL below), never
    under the owner's real account. This was originally seeded under the
    owner's own login "so the demo shows up whether you record localhost or
    the deployed site, logged in as the owner" -- which meant every one of
    the owner's real dashboards (Command Center has NO account filter at
    all) silently included these 92 fake trades in the real numbers. Moved
    2026-09-16: created a separate login specifically for this, migrated
    the existing 93 rows to it, and pointed this script at that login going
    forward so a re-run never repeats the mistake.
  - This writes to whatever database `database.py` resolves to (DATABASE_URL) —
    on this machine that's the same Postgres the live site uses. To record
    marketing content, log in as the demo account instead of the owner.

Usage:
    python seed_marketing_demo.py            # insert (safe to re-run — idempotent upsert)
    python seed_marketing_demo.py --preview  # compute + print stats only, no DB write
    python seed_marketing_demo.py --wipe     # delete every MARKETING-DEMO row, all tenants

When you're done recording, just run --wipe.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
# Moved into scripts/ during the 2026-09-16 cleanup -- put the repo root
# back on sys.path so `import database` etc. still resolve when this is
# run directly as `python scripts/seed_marketing_demo.py`.
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

import database
import tenant
import analytics

ACCOUNT_ID = "MARKETING-DEMO"
STARTING_BALANCE = 25000.0
# The dedicated login this demo data belongs under -- NOT the owner's real
# account. See the module docstring for why that separation matters.
DEMO_LOGIN_EMAIL = "demo@gmail.com"

# (symbol, pick-weight, starting price, per-trade random-walk step size,
#  $ per 1.0-point move per 1.0 lot, (min lot, max lot))
SYMBOLS = [
    ("EURUSD", 0.28, 1.0950, 0.0035, 100_000, (0.5, 3.0)),
    ("GBPUSD", 0.20, 1.2750, 0.0045, 100_000, (0.5, 2.5)),
    ("USDJPY", 0.20, 151.50, 0.45, 100_000 / 151.5, (0.5, 2.5)),
    ("XAUUSD", 0.32, 2530.0, 14.0, 100, (0.05, 0.30)),
]

TAGS = [
    "Liquidity Sweep", "Order Block", "FVG Retest",
    "Breakout Retest", "Trend Pullback", "Range Reversal",
]

NOTES_POOL = [
    "Clean sweep of the session low before the reversal — waited for the confirmation candle.",
    "Followed the plan: took partials at 1R, let the rest run into the level.",
    "Entry was a little early, price wicked below the stop before running — a process lesson, not a mistake.",
    "Textbook pullback into the order block, high conviction.",
    "Chased this one a bit — entry was late, sized down accordingly.",
    "Held through the initial pullback per the plan; would size up next time.",
]

DECIMALS = {"EURUSD": 5, "GBPUSD": 5, "USDJPY": 3, "XAUUSD": 2}


def _business_days(start: datetime, end: datetime):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def generate_trades(seed: int = 7) -> list[dict]:
    rnd = random.Random(seed)
    end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    start_date = end_date - timedelta(days=88)
    days = list(_business_days(start_date, end_date))

    price_state = {s[0]: s[2] for s in SYMBOLS}
    weights = [s[1] for s in SYMBOLS]
    by_symbol = {s[0]: s for s in SYMBOLS}

    trades = []
    idx = 0
    for day in days:
        n_today = rnd.choices([0, 1, 2, 3], weights=[18, 32, 30, 20])[0]
        for _ in range(n_today):
            sym = rnd.choices([s[0] for s in SYMBOLS], weights=weights)[0]
            _, _, _, vol_step, mult, lot_range = by_symbol[sym]
            price_state[sym] += rnd.gauss(0, vol_step)
            entry_price = price_state[sym]

            direction = rnd.choice(["BUY", "SELL"])
            is_win = rnd.random() < 0.55
            if is_win:
                gross = rnd.uniform(260, 480) if rnd.random() < 0.10 else rnd.uniform(40, 220)
            else:
                gross = -(rnd.uniform(190, 300) if rnd.random() < 0.08 else rnd.uniform(35, 150))

            lot = round(rnd.uniform(*lot_range), 2)
            price_delta = abs(gross) / max(lot * mult, 1e-9)
            sign = 1 if gross >= 0 else -1
            price_move = sign * price_delta if direction == "BUY" else -sign * price_delta
            exit_price = entry_price + price_move

            entry_dt = day.replace(
                hour=rnd.randint(1, 20), minute=rnd.choice([0, 15, 30, 45]), second=0, microsecond=0,
            )
            dur_minutes = rnd.choice([20, 35, 50, 75, 110, 160, 220, 340])
            exit_dt = entry_dt + timedelta(minutes=dur_minutes)

            commission = -round(lot * rnd.uniform(3.0, 7.0), 2)
            swap = round(rnd.uniform(-2.5, 1.0), 2)
            gross = round(gross, 2)
            net = round(gross + commission + swap, 2)

            idx += 1
            dec = DECIMALS[sym]
            trades.append({
                "trade_seq": idx,
                "symbol": sym,
                "direction": direction,
                "volume": lot,
                "entry_price": round(entry_price, dec),
                "exit_price": round(exit_price, dec),
                "commission": commission,
                "swap": swap,
                "gross_profit": gross,
                "net_profit": net,
                "entry_time": entry_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "exit_time": exit_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duration_minutes": float(dur_minutes),
                "setup_tag": rnd.choice(TAGS),
                "notes": rnd.choice(NOTES_POOL) if rnd.random() < 0.22 else None,
                "rating": rnd.choice([3, 4, 4, 5]) if is_win else rnd.choice([2, 3]),
            })
    return trades


def preview(trades: list[dict]) -> None:
    df = pd.DataFrame(trades)
    metrics = analytics.calculate_performance_metrics(df, initial_balance=STARTING_BALANCE)
    print(f"trades:          {metrics['total_trades']}")
    print(f"win rate:        {metrics['win_rate']:.1f}%")
    print(f"profit factor:   {metrics['profit_factor']}")
    print(f"net P&L:         ${metrics['total_net_pnl']:.2f}")
    print(f"gain:            {metrics['gain_pct']:.1f}%")
    print(f"final balance:   ${metrics['final_balance']:.2f}")
    print(f"max drawdown:    {metrics['max_drawdown_pct']:.1f}% (${metrics['max_drawdown_usd']:.2f})")
    print(f"sqn:             {metrics['sqn']:.2f}")
    print(f"expectancy:      ${metrics['expectancy']:.2f}/trade")
    date_min = min(t["entry_time"] for t in trades)
    date_max = max(t["exit_time"] for t in trades)
    print(f"date range:      {date_min} -> {date_max}")


def _resolve_target_user_ids() -> list[str]:
    """The dedicated demo login's id only. Deliberately NOT the owner's real
    account and NOT the passphrase-mode "local" tenant -- either of those
    would put fake trades in front of a real dashboard again. If the demo
    login doesn't exist yet, create it (see create_demo_login below) rather
    than silently falling back to something that reintroduces the bug this
    was fixed for."""
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"SELECT id FROM users WHERE lower(email) = {ph}", (DEMO_LOGIN_EMAIL,))
        row = cur.fetchone()
        if row:
            uid = row[0] if not isinstance(row, dict) else row.get("id")
            return [uid]
    finally:
        conn.close()
    sys.exit(
        f"No login found for {DEMO_LOGIN_EMAIL}. Create the dedicated demo "
        f"account first (see docs/ for how this was set up 2026-09-16) -- "
        f"refusing to fall back to the owner's account or 'local'."
    )


def insert(trades: list[dict]) -> None:
    user_ids = _resolve_target_user_ids()
    print(f"seeding under user_id(s): {user_ids}")

    final_balance = STARTING_BALANCE + sum(t["net_profit"] for t in trades)

    for uid in user_ids:
        rows = []
        for t in trades:
            row = {k: v for k, v in t.items() if k != "trade_seq"}
            row["trade_id"] = f"MKTDEMO-{t['trade_seq']:04d}-{uid}"
            row["account_id"] = ACCOUNT_ID
            row["user_id"] = uid
            rows.append(row)
        database.save_closed_trades(rows)

        token = tenant.bind(uid)
        try:
            database.save_account_balance(ACCOUNT_ID, final_balance, final_balance, "USD")
            database.set_setting(f"analytics_initial_balance::{uid}::{ACCOUNT_ID}", str(STARTING_BALANCE))
        finally:
            tenant.release(token)
        print(f"  {uid}: {len(rows)} trades inserted, balance set to ${final_balance:,.2f}")


def wipe() -> None:
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        for table in ("closed_trades", "account_metadata"):
            cur.execute(f"DELETE FROM {table} WHERE account_id = {ph}", (ACCOUNT_ID,))
            print(f"  deleted from {table}: {cur.rowcount} row(s)")
        cur.execute(f"DELETE FROM app_settings WHERE key LIKE {ph}", (f"analytics_initial_balance::%::{ACCOUNT_ID}",))
        print(f"  deleted from app_settings: {cur.rowcount} row(s)")
        conn.commit()
    finally:
        conn.close()
    database.invalidate_db_cache("closed_trades")
    print("MARKETING-DEMO fully removed.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="print stats only, no DB write")
    ap.add_argument("--wipe", action="store_true", help="delete every MARKETING-DEMO row")
    ap.add_argument("--seed", type=int, default=77)
    args = ap.parse_args()

    if args.wipe:
        wipe()
        sys.exit(0)

    trades = generate_trades(seed=args.seed)
    preview(trades)
    if not args.preview:
        insert(trades)
        database.invalidate_db_cache("closed_trades")
        print("\nDone. Log in as the owner and select account 'MARKETING-DEMO' in Analytics / Journal / Command Center.")
