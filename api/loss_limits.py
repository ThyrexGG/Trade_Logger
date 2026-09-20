# -*- coding: utf-8 -*-
"""
Loss-limit alerts: a per-account daily-loss limit (money) and a drawdown limit (% below the account's
peak balance). When closed trades push an account to 80% of a limit (a warning) or to 100% (reached),
one notification goes to the user's own phone + desktop through the trade-event feed.

Read/compute over `closed_trades` only — realized results, so an open position's floating loss is not
counted (say so wherever this is shown). It reports; it never closes, blocks or places anything.

Config is one JSON blob per user in `user_settings` (key `loss_limits`): {account: {daily_loss, drawdown_pct}}.
Each notification has a deterministic event key (account + kind + level + period), and the event log
drops a repeated key, so a limit that stays breached does not re-notify every cycle:
  daily     -> once per level per calendar day
  drawdown  -> once per level per peak (a new high re-arms it)
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

import database
import tenant

log = logging.getLogger(__name__)

SETTING_KEY = "loss_limits"
WARN_RATIO = 0.8


def _utc_today() -> date:
    """'Today' is the UTC calendar day, as trade times are stored — not the machine's local date, which
    disagrees with them for part of every day anywhere east or west of UTC."""
    return datetime.now(timezone.utc).date()


def _load_raw() -> Dict[str, Dict[str, Any]]:
    raw = database.get_user_setting(SETTING_KEY, "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get_limits() -> Dict[str, Dict[str, Optional[float]]]:
    """{account: {"daily_loss": float|None, "drawdown_pct": float|None}} for the current tenant."""
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for acct, cfg in _load_raw().items():
        if not isinstance(cfg, dict):
            continue
        d = _pos(cfg.get("daily_loss"))
        p = _pos(cfg.get("drawdown_pct"))
        if d is not None or p is not None:
            out[str(acct)] = {"daily_loss": d, "drawdown_pct": p}
    return out


def _pos(value: Any) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 and v == v and v != float("inf") else None


def set_limits(account: str, daily_loss: Optional[float], drawdown_pct: Optional[float]) -> Dict[str, Optional[float]]:
    """Save (or, with both empty, remove) one account's limits. Returns what is now stored."""
    data = get_limits()
    d, p = _pos(daily_loss), _pos(drawdown_pct)
    if p is not None and p >= 100:
        raise ValueError("drawdown_pct must be below 100")
    if d is None and p is None:
        data.pop(account, None)
    else:
        data[account] = {"daily_loss": d, "drawdown_pct": p}
    database.set_user_setting(SETTING_KEY, json.dumps(data))
    return data.get(account, {"daily_loss": None, "drawdown_pct": None})


def _saved_start_balance(account: str) -> Optional[float]:
    raw = database.get_setting(f"analytics_initial_balance::{tenant.current_user_id()}::{account}", "")
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _account_trades(account: str) -> pd.DataFrame:
    df = database.get_closed_trades(ttl_sec=database.CACHE_TTL_CLOSED_TRADES)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[df["account_id"].astype(str) == account].copy()
    if df.empty:
        return df
    df["exit_time"] = pd.to_datetime(df["exit_time"], format="mixed", utc=True).dt.tz_localize(None)
    return df.sort_values("exit_time")


def account_ids() -> List[str]:
    """Every account the user has trades on, plus any with limits saved."""
    ids = set(get_limits().keys())
    df = database.get_closed_trades(ttl_sec=database.CACHE_TTL_CLOSED_TRADES)
    if df is not None and not df.empty:
        ids.update(str(a) for a in df["account_id"].dropna().unique())
    return sorted(ids)


def compute_status(account: str, limits: Optional[Dict[str, Optional[float]]] = None) -> Dict[str, Any]:
    """Where one account stands against its limits. Missing limits give `None` ratios, not zeros."""
    limits = limits if limits is not None else get_limits().get(account, {})
    daily_limit = limits.get("daily_loss")
    dd_limit = limits.get("drawdown_pct")
    df = _account_trades(account)

    today_pnl = 0.0
    if not df.empty:
        today_df = df[df["exit_time"].dt.date == _utc_today()]
        today_pnl = float(today_df["net_profit"].sum()) if not today_df.empty else 0.0
    today_loss = max(0.0, -today_pnl)

    start = _saved_start_balance(account)
    start_source = "saved" if start is not None else None
    if start is None and not df.empty:
        # no saved starting balance: back it out of the broker balance, when there is one
        bal = database.get_account_balances().get(account)
        if bal:
            derived = float(bal["balance"]) - float(df["net_profit"].sum())
            if derived > 0:
                start, start_source = derived, "broker"

    peak = current = drawdown_pct = None
    peak_at: Optional[str] = None
    if start is not None:
        equity = start
        peak = start
        peak_at = "start"
        for _, row in df.iterrows():
            equity += float(row["net_profit"])
            if equity >= peak:
                peak, peak_at = equity, str(row["exit_time"])
        current = equity
        drawdown_pct = max(0.0, (peak - current) / peak * 100.0) if peak > 0 else 0.0

    return {
        "account_id": account,
        "daily_loss_limit": daily_limit,
        "drawdown_limit_pct": dd_limit,
        "today_net_pnl": round(today_pnl, 2),
        "today_loss": round(today_loss, 2),
        "daily_ratio": round(today_loss / daily_limit, 4) if daily_limit else None,
        "starting_balance": round(start, 2) if start is not None else None,
        "starting_balance_source": start_source,
        "peak_balance": round(peak, 2) if peak is not None else None,
        "current_balance": round(current, 2) if current is not None else None,
        "drawdown_pct": round(drawdown_pct, 2) if drawdown_pct is not None else None,
        "drawdown_ratio": round(drawdown_pct / dd_limit, 4) if (dd_limit and drawdown_pct is not None) else None,
        "drawdown_needs_balance": bool(dd_limit) and start is None,
        "_peak_at": peak_at,
    }


def _level(ratio: Optional[float]) -> Optional[str]:
    if ratio is None:
        return None
    if ratio >= 1.0:
        return "reached"
    if ratio >= WARN_RATIO:
        return "warn"
    return None


def check(logfn=log.info) -> int:
    """Evaluate every limit the current tenant has set; record a notification for each newly crossed
    level. Returns how many new events were recorded."""
    limits = get_limits()
    if not limits:
        return 0
    import trade_notify

    fired = 0
    for account, lim in limits.items():
        st = compute_status(account, lim)

        level = _level(st["daily_ratio"])
        if level:
            label = "reached" if level == "reached" else "close to"
            title = f"Daily loss limit {label} — {account}"
            body = (f"Closed trades on {account} are down ${st['today_loss']:,.2f} today; "
                    f"your daily loss limit is ${lim['daily_loss']:,.2f}.")
            key = f"risk:{account}:daily:{level}:{_utc_today().isoformat()}"
            if trade_notify.record_risk_alert(key, title, body, account, -st["today_loss"]) is not None:
                fired += 1
                logfn(f"Loss limit ({level}): {account} daily")

        level = _level(st["drawdown_ratio"])
        if level:
            label = "reached" if level == "reached" else "close to"
            title = f"Drawdown limit {label} — {account}"
            body = (f"{account} is {st['drawdown_pct']:.1f}% below its peak balance of ${st['peak_balance']:,.2f}; "
                    f"your drawdown limit is {lim['drawdown_pct']:g}%.")
            key = f"risk:{account}:dd:{level}:{st['_peak_at']}"
            if trade_notify.record_risk_alert(key, title, body, account, None) is not None:
                fired += 1
                logfn(f"Loss limit ({level}): {account} drawdown")
    return fired
