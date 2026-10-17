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

import hashlib
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

import capital_sync
import database

WINDOW_DAYS = 30
TX_PAGE_LIMIT = 500                 # same cap the normal sync asks for
STOP_AFTER_EMPTY_DAYS = 1095        # 3 years with no trades at all = start of history (a quiet
                                    # patch of months must not end the walk early; an empty
                                    # window costs one cheap call)
HISTORY_FLOOR = datetime(2016, 1, 1, tzinfo=timezone.utc)
REQUEST_GAP_SEC = 0.15
_RETRIES = 3

# Capital.com is strict about logins (POST /session is 1/s per API key and it
# answers 429 well before that if you log in dozens of times in a few minutes),
# and a session stays valid for 10 idle minutes -- so log in once and reuse the
# tokens across slices instead of logging in per slice.
_SESSION_TTL_SEC = 8 * 60
_LOGIN_RETRY_WAITS = (2.0, 4.0, 8.0)
_sessions: Dict[str, Dict[str, Any]] = {}
_sessions_lock = threading.Lock()


class BackfillError(Exception):
    """A slice could not be completed; nothing from it was saved.
    ``retryable`` = Capital.com was rate-limiting / briefly down; trying the
    same slice again after a wait is expected to work. ``status`` is Capital.com's
    HTTP status when there was one."""

    def __init__(self, message: str, *, status: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


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
    raise BackfillError(
        f"Capital.com answered {res.status_code} for {url.rsplit('/', 1)[-1]}",
        status=res.status_code, retryable=res.status_code in (429, 500, 502, 503, 504),
    )


def _login(session: requests.Session, creds: Dict[str, Any]):
    base = capital_sync.DEMO_API_URL if creds.get("is_demo") else capital_sync.LIVE_API_URL
    headers = {"X-CAP-API-KEY": str(creds.get("api_key") or "").strip(), "Content-Type": "application/json"}
    body = {"identifier": str(creds.get("email") or "").strip(),
            "password": str(creds.get("password") or "").strip()}
    res = None
    for wait in (*_LOGIN_RETRY_WAITS, None):
        res = session.post(f"{base}/session", headers=headers, json=body, timeout=30)
        if res.status_code != 429 or wait is None:
            break
        time.sleep(wait)
    cst, token = res.headers.get("CST"), res.headers.get("X-SECURITY-TOKEN")
    if res.status_code != 200 or not cst or not token:
        raise BackfillError(
            f"Capital.com login failed ({res.status_code})",
            status=res.status_code, retryable=res.status_code in (429, 500, 502, 503, 504),
        )
    headers.update({"CST": cst, "X-SECURITY-TOKEN": token})
    return base, headers


def _cache_key(creds: Dict[str, Any]) -> str:
    raw = f"{creds.get('api_key')}|{creds.get('email')}|{bool(creds.get('is_demo'))}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _auth(session: requests.Session, creds: Dict[str, Any], *, fresh: bool = False):
    """(base, headers, reused) -- reuses a recent login unless ``fresh``."""
    key = _cache_key(creds)
    now = time.monotonic()
    with _sessions_lock:
        hit = _sessions.get(key)
        if hit and not fresh and now - hit["at"] < _SESSION_TTL_SEC:
            hit["at"] = now                      # Capital.com's 10 minutes are idle minutes
            return hit["base"], hit["headers"], True
    base, headers = _login(session, creds)
    with _sessions_lock:
        _sessions[key] = {"base": base, "headers": headers, "at": time.monotonic()}
    return base, headers, False


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


def _collect(session, base, headers, start: datetime, end: datetime, now: datetime):
    """Everything Capital.com has for [start, end]: the closed-trade transactions
    and, for the days that matter, their activity records. Nothing is written."""
    txs = _fetch_transactions(session, base, headers, start, end)
    closed = [t for t in txs if t.get("transactionType") == "TRADE" and t.get("note") == "Trade closed"]
    activities: Dict[str, List[dict]] = {}
    if closed:
        for day in _activity_days(closed, now):
            res = _get(session, f"{base}/history/activity", headers, {
                "from": _fmt(day), "to": _fmt(min(day + timedelta(days=1), now)), "detailed": "true",
            })
            for act in res.json().get("activities", []) or []:
                if act.get("dealId"):
                    activities.setdefault(act["dealId"], []).append(act)
    return closed, activities


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
    base, headers, reused = _auth(session, creds)
    try:
        closed, activities = _collect(session, base, headers, start, end, now)
    except BackfillError as exc:
        if not (reused and exc.status == 401):
            raise
        # the reused login had expired -- log in afresh and redo this slice once
        base, headers, _ = _auth(session, creds, fresh=True)
        closed, activities = _collect(session, base, headers, start, end, now)

    trades: List[dict] = []
    if closed:
        trades, raw_deals = capital_sync.reconstruct_closed_trades(account_id, closed, activities)
        if trades:
            database.save_raw_deals(raw_deals)
            database.save_closed_trades(trades)

    # Closes Capital.com listed but whose detail records it did not return can't
    # be rebuilt (direction / prices live there). Count them so the page can say so
    # instead of silently looking like the history just ends.
    saved_ids = {str(t["trade_id"]).split("_")[0] for t in trades}
    skipped_dates = [str(t.get("dateUtc")) for t in closed if str(t.get("dealId")) not in saved_ids]

    span_days = max(1, (end - start).days)
    empty = 0 if closed else max(0, int(empty_days)) + span_days
    done = start <= HISTORY_FLOOR or empty >= STOP_AFTER_EMPTY_DAYS
    exits = [str(t["exit_time"]) for t in trades if t.get("exit_time")]
    return {
        "skipped": len(skipped_dates),
        "oldest_skipped": min(skipped_dates) if skipped_dates else None,
        "imported": len(trades),
        "next_before": _fmt(start),
        "empty_days": empty,
        "done": done,
        "window_from": _fmt(start),
        "oldest_trade": min(exits) if exits else None,
    }
