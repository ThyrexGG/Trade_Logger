# -*- coding: utf-8 -*-
"""
Weekly performance summary: once a week, one notification with how the week went — net P&L, win rate,
best and worst trade, and which setup tag earned or lost the most.

Read-only over `closed_trades` (realized results). A "week" is Monday 00:00 to Sunday 24:00 UTC, the same
server day the loss limits use. The summary goes out on Sunday from 12:00 UTC and covers Monday up to that
moment; if the server was asleep then, the next sync (or the app opening) sends it as long as it is still
inside a short grace window after the week ended. One event key per user + week means it can never repeat.

It is on by default and per user (`user_settings["weekly_summary"]` = "off" to opt out). A week with no
closed trades sends nothing.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

import database
import tenant
from api import trade_groups

log = logging.getLogger(__name__)

SETTING_KEY = "weekly_summary"
SEND_AFTER = time(12, 0)     # on Sunday, UTC
SEND_WEEKDAY = 6             # Sunday
GRACE = timedelta(days=3)    # how long after a week ends a missed summary is still worth sending
MIN_TAG_TRADES = 2           # a tag needs this many trades before it is called "best" or "worst"

# (user, week start) pairs already handled this process, so the 2-minute loop does not recompute them.
_handled: Set[Tuple[str, date]] = set()


def is_enabled(user_id: Optional[str] = None) -> bool:
    try:
        return (database.get_user_setting(SETTING_KEY, "", user_id=user_id) or "").strip().lower() != "off"
    except Exception:  # noqa: BLE001
        return True


def set_enabled(enabled: bool) -> None:
    database.set_user_setting(SETTING_KEY, "" if enabled else "off")


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _utc_start(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=timezone.utc)


def week_key(start: date) -> str:
    iso = start.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _text(value: Any) -> str:
    return "" if value is None or (isinstance(value, float) and value != value) else str(value).strip()


def _money(v: float) -> str:
    return f"{'+' if v >= 0 else '-'}${abs(v):,.2f}"


def summarize(start: date) -> Dict[str, Any]:
    """The current tenant's closed trades for the week beginning `start` (a Monday, UTC), all accounts."""
    end = start + timedelta(days=7)
    out: Dict[str, Any] = {
        "trades": 0, "wins": 0, "losses": 0, "win_rate": None, "net": 0.0, "profit_factor": None,
        "best_trade": None, "worst_trade": None, "best_tag": None, "worst_tag": None,
        "untagged": 0, "by_day": [{"date": (start + timedelta(days=i)).isoformat(), "net": 0.0, "trades": 0} for i in range(7)],
        "by_tag": [],
    }
    df = trade_groups.folded_dataframe(database.get_closed_trades(ttl_sec=database.CACHE_TTL_CLOSED_TRADES))
    if df is None or df.empty:
        return out
    df = df.copy()
    df["exit_time"] = pd.to_datetime(df["exit_time"], format="mixed", utc=True).dt.tz_localize(None)
    lo = pd.Timestamp(datetime.combine(start, time(0, 0)))
    hi = pd.Timestamp(datetime.combine(end, time(0, 0)))
    df = df[(df["exit_time"] >= lo) & (df["exit_time"] < hi)]
    if df.empty:
        return out
    net = pd.to_numeric(df["net_profit"], errors="coerce").fillna(0.0)
    df = df.assign(_net=net, _tag=df["setup_tag"].map(_text) if "setup_tag" in df.columns else "")

    n = int(len(df))
    wins = int((df["_net"] > 0).sum())
    losses = int((df["_net"] < 0).sum())
    gross_win = float(df.loc[df["_net"] > 0, "_net"].sum())
    gross_loss = float(-df.loc[df["_net"] < 0, "_net"].sum())
    out.update(
        trades=n, wins=wins, losses=losses, win_rate=round(wins / n, 3), net=round(float(df["_net"].sum()), 2),
        profit_factor=round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        untagged=int((df["_tag"] == "").sum()),
    )
    best = df.loc[df["_net"].idxmax()]
    worst = df.loc[df["_net"].idxmin()]
    out["best_trade"] = {"symbol": _text(best["symbol"]), "net": round(float(best["_net"]), 2)}
    if float(worst["_net"]) < 0:
        out["worst_trade"] = {"symbol": _text(worst["symbol"]), "net": round(float(worst["_net"]), 2)}

    for i, day in enumerate(out["by_day"]):
        d = df[df["exit_time"].dt.date.astype(str) == day["date"]]
        day["net"], day["trades"] = round(float(d["_net"].sum()), 2), int(len(d))

    tags = []
    for tag, g in df[df["_tag"] != ""].groupby("_tag"):
        tags.append({"tag": tag, "trades": int(len(g)), "net": round(float(g["_net"].sum()), 2)})
    tags.sort(key=lambda t: t["net"], reverse=True)
    out["by_tag"] = tags
    eligible = [t for t in tags if t["trades"] >= MIN_TAG_TRADES]
    if eligible and eligible[0]["net"] > 0:
        out["best_tag"] = eligible[0]
    if eligible and eligible[-1]["net"] < 0:
        out["worst_tag"] = eligible[-1]
    return out


def message(summary: Dict[str, Any]) -> Tuple[str, str]:
    """(title, body) for the notification."""
    n = summary["trades"]
    title = f"Your week: {_money(summary['net'])} on {n} trade{'' if n == 1 else 's'}"
    parts = [f"{summary['wins']} won, {summary['losses']} lost ({round((summary['win_rate'] or 0) * 100)}% win rate)."]
    if summary["best_trade"] and summary["best_trade"]["net"] > 0:
        parts.append(f"Best: {summary['best_trade']['symbol']} {_money(summary['best_trade']['net'])}.")
    if summary["worst_trade"]:
        parts.append(f"Worst: {summary['worst_trade']['symbol']} {_money(summary['worst_trade']['net'])}.")
    if summary["best_tag"]:
        t = summary["best_tag"]
        parts.append(f"Best setup: {t['tag']} {_money(t['net'])} over {t['trades']}.")
    if summary["untagged"] and summary["untagged"] * 2 >= n:
        parts.append(f"{summary['untagged']} untagged - tag them in Setups.")
    return title, " ".join(parts)


def weeks_due(now: datetime) -> List[date]:
    """Week starts a summary may be sent for right now, oldest first."""
    cur = week_start(now.date())
    due: List[date] = []
    prev = cur - timedelta(days=7)
    if now < _utc_start(cur) + GRACE:
        due.append(prev)
    if now >= datetime.combine(cur + timedelta(days=SEND_WEEKDAY), SEND_AFTER, tzinfo=timezone.utc):
        due.append(cur)
    return due


def check(logfn=log.info, now: Optional[datetime] = None) -> int:
    """Send the current tenant's weekly summary when one is due. Returns how many were recorded (0 or 1
    normally). Cheap outside the send window: it returns before touching the database."""
    now = now or datetime.now(timezone.utc)
    due = weeks_due(now)
    if not due or not is_enabled():
        return 0
    import trade_notify

    uid = tenant.current_user_id()
    sent = 0
    for start in due:
        if (uid, start) in _handled:
            continue
        summary = summarize(start)
        if summary["trades"] == 0:
            continue  # nothing to report yet; a trade closing later in the window is still picked up
        title, body = message(summary)
        event_id = trade_notify.record_summary(f"summary:week:{start.isoformat()}", title, body, week_key(start), summary["net"])
        _handled.add((uid, start))
        if event_id is not None:
            sent += 1
            logfn(f"Weekly summary sent for {week_key(start)}")
    return sent
