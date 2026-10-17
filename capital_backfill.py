# -*- coding: utf-8 -*-
"""
Full-history import for a Capital.com connection.

The normal sync (``capital_sync.sync_capital``) only looks 30 days back on its
first run, and Capital.com's ``/history/activity`` only answers for ONE day at
a time (``from``..``to`` is capped at 1 day), so a whole history is hundreds of
small calls. Doing that in one request would time out and hammer the API, so
the import is cut into slices and the *browser* drives it:

  * one call = one 30-day window, walking backwards from today
  * a window costs 1 transactions call + 1 activity call per day that actually
    had a close (or the day before one) -- quiet days and weekends are skipped
  * calls are spaced ~0.15 s apart (Capital.com allows 10/s)
  * the server keeps no state: the caller hands back ``before`` / ``empty_days``
    and the import stops itself after STOP_AFTER_EMPTY_DAYS days with no trades

Writes are upserts keyed on the trade id, so a slice can safely be repeated.
Read-only toward the broker -- no order path.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

import capital_sync
import database

WINDOW_DAYS = 30
TX_PAGE_LIMIT = 500                 # same cap the normal sync asks for
STOP_AFTER_EMPTY_DAYS = 180         # this long with no trades at all = start of history
HISTORY_FLOOR = datetime(2012, 1, 1, tzinfo=timezone.utc)
REQUEST_GAP_SEC = 0.15
_RETRIES = 3


class BackfillError(Exception):
    """A slice could not be completed; nothing from it was saved."""


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _parse(value: Any) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", ""))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_before(value: Optional[str], now: datetime) -> datetime:
    """The cursor the caller sends back; clamped to [HISTORY_FLOOR, now]."""
    if not value:
        return now
    dt = _parse(value)
    if dt is None:
        raise BackfillError("bad 'before' cursor")
    return max(HISTORY_FLOOR, min(dt, now))


def _get(session: requests.Session, url: str, headers: Dict[str, str], params: Dict[str, Any]):
    """GET with a short back-off on rate limits / 5xx. Always paced."""
    res = None
    for attempt in range(_RETRIES):
        time.sleep(REQUEST_GAP_SEC)
        res = session.get(url, headers=headers, params=params, timeout=30)
        if res.status_code == 200:
            return res
        if res.status_code not in (429, 500, 502, 503, 504):
            break
        time.sleep(1.0 * (attempt + 1))
    raise BackfillError(f"Capital.com answered {res.status_code} for {url.rsplit('/', 1)[-1]}")


def _login(session: requests.Session, creds: Dict[str, Any]):
    base = capital_sync.DEMO_API_URL if creds.get("is_demo") else capital_sync.LIVE_API_URL
    headers = {"X-CAP-API-KEY": str(creds.get("api_key") or "").strip(), "Content-Type": "application/json"}
    res = session.post(
        f"{base}/session", headers=headers, timeout=30,
        json={"identifier": str(creds.get("email") or "").strip(),
              "password": str(creds.get("password") or "").strip()},
    )
    cst, token = res.headers.get("CST"), res.headers.get("X-SECURITY-TOKEN")
    if res.status_code != 200 or not cst or not token:
        raise BackfillError(f"Capital.com login failed ({res.status_code})")
    headers.update({"CST": cst, "X-SECURITY-TOKEN": token})
    return base, headers


def _fetch_transactions(session, base, headers, start: datetime, end: datetime) -> List[dict]:
    """All transactions in [start, end]. A full page may be truncated (the
    endpoint has no paging), so a full page is split in half and re-asked."""
    res = _get(session, f"{base}/history/transactions", headers,
               {"from": _fmt(start), "to": _fmt(end), "limit": TX_PAGE_LIMIT})
    txs = res.json().get("transactions", []) or []
    if len(txs) >= TX_PAGE_LIMIT and (end - start) > timedelta(hours=1):
        mid = start + (end - start) / 2
        merged: Dict[str, dict] = {}
        for part in (_fetch_transactions(session, base, headers, start, mid),
                     _fetch_transactions(session, base, headers, mid, end)):
            for tx in part:
                merged[json.dumps(tx, sort_keys=True)] = tx
        return list(merged.values())
    return txs


def _activity_days(closed: List[dict], now: datetime) -> List[datetime]:
    """Midnight-UTC starts of every day worth asking activity for: the day of
    each close and the day before it (where a trade usually opened)."""
    days = set()
    for tx in closed:
        closed_at = _parse(tx.get("dateUtc"))
        if closed_at is None:
            continue
        day = closed_at.replace(hour=0, minute=0, second=0, microsecond=0)
        days.update((day, day - timedelta(days=1)))
    return sorted(d for d in days if d <= now)


def backfill_step(
    creds: Dict[str, Any], before: Optional[str] = None, empty_days: int = 0,
    *, now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Import one 30-day window ending at ``before`` (default: now). The caller
    must already be inside ``tenant.use(user)``."""
    now = now or datetime.now(timezone.utc)
    account_id = str(creds.get("account_id") or "").strip()
    if not account_id:
        raise BackfillError("this connection has no Account ID")

    end = parse_before(before, now)
    start = max(HISTORY_FLOOR, end - timedelta(days=WINDOW_DAYS))

    session = requests.Session()
    base, headers = _login(session, creds)

    txs = _fetch_transactions(session, base, headers, start, end)
    closed = [t for t in txs if t.get("transactionType") == "TRADE" and t.get("note") == "Trade closed"]

    trades: List[dict] = []
    if closed:
        activities: Dict[str, List[dict]] = {}
        for day in _activity_days(closed, now):
            res = _get(session, f"{base}/history/activity", headers, {
                "from": _fmt(day), "to": _fmt(min(day + timedelta(days=1), now)), "detailed": "true",
            })
            for act in res.json().get("activities", []) or []:
                if act.get("dealId"):
                    activities.setdefault(act["dealId"], []).append(act)
        trades, raw_deals = capital_sync.reconstruct_closed_trades(account_id, closed, activities)
        if trades:
            database.save_raw_deals(raw_deals)
            database.save_closed_trades(trades)

    span_days = max(1, (end - start).days)
    empty = 0 if closed else max(0, int(empty_days)) + span_days
    done = start <= HISTORY_FLOOR or empty >= STOP_AFTER_EMPTY_DAYS
    exits = [str(t["exit_time"]) for t in trades if t.get("exit_time")]
    return {
        "imported": len(trades),
        "next_before": _fmt(start),
        "empty_days": empty,
        "done": done,
        "window_from": _fmt(start),
        "oldest_trade": min(exits) if exits else None,
    }
