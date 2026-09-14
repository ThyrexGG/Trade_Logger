# -*- coding: utf-8 -*-
"""
Prop-firm challenge tracker (W13): per-account phase progress, drawdown
budget, daily-loss budget, and minimum-profit-day counter against a
user-configured rule set (5ers-shaped defaults, but every number is
overridable so this isn't tied to one firm).

Pure read/compute over already-authoritative sources — `database.get_closed_trades`
(the same population `analytics.py` uses) and `database.get_account_balances`
(the synced broker balance). Config is a small JSON blob in the existing
`app_settings` key-value store, scoped by tenant + account exactly like
`api/routers/analytics.py`'s saved initial balance. No import of / path to
execution, broker order, or risk-gateway code — this only ever reads trade
history and a balance, and writes a settings row.

**Not verified against 5ers' internal drawdown methodology** — "static" vs
"trailing" and whether floating P&L counts are not published with certainty
(checked 2026-09-14; the5ers.com's own explainer does not specify). Every
computed number here is an estimate for content/self-tracking purposes, and
`ChallengeStatusResponse.disclaimer` says so — never present it as a
substitute for the firm's own dashboard when a real breach is on the line.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

import database
import tenant

DEFAULTS: Dict[str, Any] = {
    "firm": "5ers",
    "account_size": 5000.0,
    "phase1_target_pct": 10.0,
    "phase2_target_pct": 5.0,
    "max_drawdown_pct": 10.0,
    "daily_loss_pct": 5.0,
    "min_profit_days": 3,
    "profit_day_threshold_pct": 0.5,
    "drawdown_mode": "trailing",  # conservative default; the firm may actually use "static"
}

DISCLAIMER = (
    "Estimated from your synced balance and closed trades — verify against "
    "your firm's own dashboard before relying on it for a real risk decision."
)


def _key(account: str) -> str:
    return f"challenge_config::{tenant.current_user_id()}::{account}"


def get_config(account: str) -> Optional[Dict[str, Any]]:
    raw = database.get_setting(_key(account), "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def save_config(account: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    """Create, or update the rule set on, this account's challenge config.
    Phase progress (phase / phase_start_balance / phase_start_date /
    created_at) is preserved on an update — editing a rule isn't a restart;
    use `reset_challenge` for that."""
    existing = get_config(account)
    today = date.today().isoformat()
    if existing is None:
        cfg = {**DEFAULTS, **rules, "account_id": account,
               "phase": "1", "phase_start_balance": float(rules.get("account_size", DEFAULTS["account_size"])),
               "phase_start_date": today, "created_at": today}
    else:
        cfg = {**existing, **rules, "account_id": account}
    database.set_setting(_key(account), json.dumps(cfg))
    return cfg


def advance_phase(account: str, to: str) -> Optional[Dict[str, Any]]:
    cfg = get_config(account)
    if cfg is None:
        return None
    status = compute_status(account)
    current_balance = status.get("current_balance")
    cfg["phase"] = to
    cfg["phase_start_balance"] = float(current_balance) if current_balance is not None else cfg["account_size"]
    cfg["phase_start_date"] = date.today().isoformat()
    database.set_setting(_key(account), json.dumps(cfg))
    return cfg


def reset_challenge(account: str) -> Optional[Dict[str, Any]]:
    cfg = get_config(account)
    if cfg is None:
        return None
    today = date.today().isoformat()
    cfg["phase"] = "1"
    cfg["phase_start_balance"] = float(cfg["account_size"])
    cfg["phase_start_date"] = today
    cfg["created_at"] = today
    database.set_setting(_key(account), json.dumps(cfg))
    return cfg


def delete_config(account: str) -> None:
    database.set_setting(_key(account), "")


def _load_trades(account: str) -> pd.DataFrame:
    df = database.get_closed_trades(ttl_sec=database.CACHE_TTL_CLOSED_TRADES)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[df["account_id"].astype(str) == account].copy()
    if df.empty:
        return df
    df["exit_time"] = pd.to_datetime(df["exit_time"], format="mixed", utc=True).dt.tz_localize(None)
    return df


def _empty_status(account: str) -> Dict[str, Any]:
    return {
        "configured": False, "account_id": account, "config": None,
        "current_balance": None, "phase": None, "phase_target_pct": None,
        "phase_start_balance": None, "phase_progress_pct": None, "phase_progress_ratio": None,
        "phase_gain_amount": None, "phase_target_amount": None,
        "drawdown_mode": None, "peak_balance": None, "drawdown_floor_balance": None,
        "drawdown_used_pct": None, "drawdown_budget_used_ratio": None,
        "daily_loss_today_amount": None, "daily_loss_used_pct": None, "daily_loss_budget_used_ratio": None,
        "profit_days_count": None, "min_profit_days": None, "profit_day_dates": [],
        "disclaimer": DISCLAIMER, "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compute_status(account: str) -> Dict[str, Any]:
    cfg = get_config(account)
    if cfg is None:
        return _empty_status(account)

    account_size = float(cfg["account_size"])
    phase = cfg["phase"]
    phase_start_balance = float(cfg["phase_start_balance"])
    df = _load_trades(account)

    balances = database.get_account_balances()
    entry = balances.get(account)
    live_balance = float(entry["balance"]) if entry else None

    # --- running equity + peak since the challenge began (for drawdown) ---
    since_inception = df[df["exit_time"] >= pd.Timestamp(cfg["created_at"])] if not df.empty else df
    running = account_size
    peak = account_size
    if not since_inception.empty:
        for pnl in since_inception.sort_values("exit_time")["net_profit"]:
            running += float(pnl)
            peak = max(peak, running)
    current_balance = live_balance if live_balance is not None else running
    peak = max(peak, current_balance)

    max_dd_pct = float(cfg["max_drawdown_pct"])
    if cfg["drawdown_mode"] == "static":
        floor_balance = account_size * (1 - max_dd_pct / 100.0)
        dd_used_pct = max(0.0, (account_size - current_balance) / account_size * 100.0)
    else:  # trailing
        floor_balance = peak * (1 - max_dd_pct / 100.0)
        dd_used_pct = max(0.0, (peak - current_balance) / peak * 100.0) if peak > 0 else 0.0
    dd_budget_ratio = min(1.0, dd_used_pct / max_dd_pct) if max_dd_pct > 0 else 0.0

    # --- today's P&L vs the daily-loss budget ---
    today = date.today()
    today_df = df[df["exit_time"].dt.date == today] if not df.empty else df
    today_pnl = float(today_df["net_profit"].sum()) if not today_df.empty else 0.0
    daily_loss_pct_cfg = float(cfg["daily_loss_pct"])
    daily_loss_used_pct = max(0.0, -today_pnl / account_size * 100.0) if account_size > 0 else 0.0
    daily_loss_budget_ratio = min(1.0, daily_loss_used_pct / daily_loss_pct_cfg) if daily_loss_pct_cfg > 0 else 0.0

    # --- profit days since this phase started ---
    phase_df = df[df["exit_time"] >= pd.Timestamp(cfg["phase_start_date"])] if not df.empty else df
    threshold_amount = account_size * float(cfg["profit_day_threshold_pct"]) / 100.0
    profit_day_dates: List[str] = []
    if not phase_df.empty:
        daily_sums = phase_df.groupby(phase_df["exit_time"].dt.date)["net_profit"].sum()
        profit_day_dates = sorted(str(d) for d, v in daily_sums.items() if float(v) >= threshold_amount)

    # --- phase progress (no target once funded) ---
    phase_target_pct: Optional[float] = None
    if phase == "1":
        phase_target_pct = float(cfg["phase1_target_pct"])
    elif phase == "2":
        phase_target_pct = float(cfg["phase2_target_pct"])

    phase_gain = current_balance - phase_start_balance
    phase_progress_pct = (phase_gain / phase_start_balance * 100.0) if phase_start_balance > 0 else 0.0
    phase_target_amount = (phase_start_balance * phase_target_pct / 100.0) if phase_target_pct is not None else None
    phase_progress_ratio = (
        min(1.0, max(0.0, phase_progress_pct / phase_target_pct)) if phase_target_pct else None
    )

    return {
        "configured": True,
        "account_id": account,
        "config": cfg,
        "current_balance": round(current_balance, 2),
        "phase": phase,
        "phase_target_pct": phase_target_pct,
        "phase_start_balance": round(phase_start_balance, 2),
        "phase_progress_pct": round(phase_progress_pct, 2),
        "phase_progress_ratio": round(phase_progress_ratio, 4) if phase_progress_ratio is not None else None,
        "phase_gain_amount": round(phase_gain, 2),
        "phase_target_amount": round(phase_target_amount, 2) if phase_target_amount is not None else None,
        "drawdown_mode": cfg["drawdown_mode"],
        "peak_balance": round(peak, 2),
        "drawdown_floor_balance": round(floor_balance, 2),
        "drawdown_used_pct": round(dd_used_pct, 2),
        "drawdown_budget_used_ratio": round(dd_budget_ratio, 4),
        "daily_loss_today_amount": round(today_pnl, 2),
        "daily_loss_used_pct": round(daily_loss_used_pct, 2),
        "daily_loss_budget_used_ratio": round(daily_loss_budget_ratio, 4),
        "profit_days_count": len(profit_day_dates),
        "min_profit_days": int(cfg["min_profit_days"]),
        "profit_day_dates": profit_day_dates,
        "disclaimer": DISCLAIMER,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
