#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradeLogger MT5 push agent  (platform plan W9)
=============================================

Runs on YOUR Windows PC, next to your MetaTrader 5 terminal. It reads your
closed deals, open positions and balance from MT5 and sends them to a
TradeLogger server over HTTPS. That's all it does:

  * It never places, modifies or closes an order.
  * It only ever writes YOUR data (the server ties every row to your login).
  * It needs the MT5 terminal installed and, ideally, already running and
    logged in to the account you want to track.

Setup and a scheduled-task installer are in  README.md  (same folder).

    python mt5_push_agent.py --once       # one sync, then exit
    python mt5_push_agent.py --daemon     # sync now, then every N minutes
    python mt5_push_agent.py --check      # verify config + connectivity only

Requires:  pip install MetaTrader5 requests
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Run:  pip install MetaTrader5 requests")

try:
    import MetaTrader5 as mt5
except ImportError:
    sys.exit(
        "MetaTrader5 package not found. Run:  pip install MetaTrader5\n"
        "(it only works on Windows, with the MT5 terminal installed)"
    )

AGENT_VERSION = "1.0.0"
DEFAULT_CONFIG = Path(__file__).with_name("mt5_agent_config.json")
HISTORY_FALLBACK_START = datetime(2020, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #
def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        sys.exit(
            f"Config not found: {path}\n"
            f"Copy mt5_agent_config.example.json to {path.name} and fill it in."
        )
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"Config is not valid JSON: {exc}")

    if not cfg.get("server_url"):
        sys.exit("Config: 'server_url' is required (your TradeLogger backend URL).")
    cfg["server_url"] = cfg["server_url"].rstrip("/")
    has_supabase = bool(cfg.get("supabase_url") and cfg.get("supabase_anon_key"))
    has_passphrase = bool(cfg.get("passphrase"))
    if not (has_supabase or has_passphrase):
        sys.exit(
            "Config: provide either supabase_url + supabase_anon_key + email + password\n"
            "        (multi-user mode) OR passphrase (single-user mode)."
        )
    if has_supabase and not (cfg.get("email") and cfg.get("password")):
        sys.exit("Config: 'email' and 'password' are required with Supabase auth.")
    cfg.setdefault("poll_minutes", 15)
    return cfg


# --------------------------------------------------------------------------- #
#  Auth  -> a bearer token for the TradeLogger API
# --------------------------------------------------------------------------- #
class Auth:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self._token: Optional[str] = None
        self._refresh: Optional[str] = None
        self._expires_at: float = 0.0
        self._mode = "supabase" if cfg.get("supabase_url") else "passphrase"

    def bearer(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        if self._mode == "supabase":
            self._supabase_login()
        else:
            self._passphrase_login()
        return self._token or ""

    def _supabase_login(self) -> None:
        base = self.cfg["supabase_url"].rstrip("/")
        headers = {
            "apikey": self.cfg["supabase_anon_key"],
            "Content-Type": "application/json",
        }
        if self._refresh:
            r = requests.post(
                f"{base}/auth/v1/token?grant_type=refresh_token",
                headers=headers,
                json={"refresh_token": self._refresh},
                timeout=20,
            )
            if r.status_code == 200:
                self._store(r.json())
                return
        r = requests.post(
            f"{base}/auth/v1/token?grant_type=password",
            headers=headers,
            json={"email": self.cfg["email"], "password": self.cfg["password"]},
            timeout=20,
        )
        if r.status_code != 200:
            sys.exit(f"Supabase login failed ({r.status_code}): {r.text[:300]}")
        self._store(r.json())

    def _store(self, data: Dict[str, Any]) -> None:
        self._token = data.get("access_token")
        self._refresh = data.get("refresh_token") or self._refresh
        self._expires_at = time.time() + float(data.get("expires_in", 3600))
        if not self._token:
            sys.exit("Supabase returned no access_token.")

    def _passphrase_login(self) -> None:
        r = requests.post(
            f"{self.cfg['server_url']}/api/auth/login",
            json={"password": self.cfg["passphrase"]},
            timeout=20,
        )
        if r.status_code != 200:
            sys.exit(f"Passphrase login failed ({r.status_code}): {r.text[:300]}")
        body = r.json()
        self._token = body.get("token") or body.get("access_token")
        self._expires_at = time.time() + 3600
        if not self._token:
            sys.exit("Login endpoint returned no token.")


# --------------------------------------------------------------------------- #
#  MT5 read
# --------------------------------------------------------------------------- #
def mt5_connect(cfg: Dict[str, Any]) -> None:
    mt5_cfg = cfg.get("mt5") or {}
    login, password, server = (
        mt5_cfg.get("login"),
        mt5_cfg.get("password"),
        mt5_cfg.get("server"),
    )
    ok = False
    if login and password and server:
        ok = mt5.initialize(
            login=int(login), password=str(password), server=str(server), timeout=15000
        )
    if not ok:
        ok = mt5.initialize(timeout=15000)
    if not ok:
        sys.exit(
            f"Could not connect to MT5 (error {mt5.last_error()}).\n"
            "Open the MT5 terminal and log in to the account you want to track."
        )


def read_snapshot(server_cursor_ts: int) -> Dict[str, Any]:
    acc = mt5.account_info()
    if acc is None:
        sys.exit(f"MT5 account_info() failed (error {mt5.last_error()}).")
    account_id = f"MT5_{acc.login}"

    balance = {
        "balance": float(acc.balance),
        "equity": float(acc.equity),
        "currency": getattr(acc, "currency", "USD") or "USD",
    }

    positions = []
    for p in mt5.positions_get() or []:
        positions.append(
            {
                "position_id": f"MT5_{p.ticket}",
                "symbol": p.symbol,
                "direction": "BUY" if p.type == 0 else "SELL",
                "volume": float(p.volume),
                "entry_price": float(p.price_open),
                "current_price": float(p.price_current),
                "sl": float(p.sl or 0.0),
                "tp": float(p.tp or 0.0),
                "floating_pnl": float(p.profit),
                "swap": float(p.swap or 0.0),
                "open_time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
            }
        )

    if server_cursor_ts > 0:
        start = datetime.fromtimestamp(server_cursor_ts - 10, tz=timezone.utc)
    else:
        start = HISTORY_FALLBACK_START
    end = datetime.now(timezone.utc) + timedelta(days=2)

    deals = []
    for d in mt5.history_deals_get(start, end) or []:
        if d.type not in (0, 1):  # keep only buy/sell legs
            continue
        deals.append(
            {
                "deal_id": str(d.ticket),
                "symbol": d.symbol,
                "type": "BUY" if d.type == 0 else "SELL",
                "volume": float(d.volume),
                "price": float(d.price),
                "commission": float(d.commission),
                "swap": float(d.swap),
                "profit": float(d.profit),
                "timestamp": int(d.time),
                "position_id": str(d.position_id),
            }
        )

    return {
        "account_id": account_id,
        "agent_version": AGENT_VERSION,
        "balance": balance,
        "positions": positions,
        "deals": deals,
        "_login": acc.login,
        "_company": getattr(acc, "company", ""),
    }


# --------------------------------------------------------------------------- #
#  Sync
# --------------------------------------------------------------------------- #
def get_cursor(cfg: Dict[str, Any], auth: Auth, account_id: str) -> int:
    r = requests.get(
        f"{cfg['server_url']}/api/ingest/mt5/cursor",
        params={"account": account_id},
        headers={"Authorization": f"Bearer {auth.bearer()}"},
        timeout=20,
    )
    if r.status_code == 401:
        sys.exit("Server rejected the token (401). Check email/password and the allowlist.")
    if r.status_code != 200:
        print(f"  ! cursor lookup failed ({r.status_code}); doing a full history pull")
        return 0
    return int(r.json().get("last_deal_timestamp") or 0)


def push(cfg: Dict[str, Any], auth: Auth, snapshot: Dict[str, Any]) -> None:
    payload = {k: v for k, v in snapshot.items() if not k.startswith("_")}
    # chunk large first-run histories so we stay well under the server cap
    deals = payload.pop("deals")
    chunk = 5000
    chunks = [deals[i : i + chunk] for i in range(0, len(deals), chunk)] or [[]]
    for idx, part in enumerate(chunks):
        body = {**payload, "deals": part}
        # only send the balance/position snapshot on the last chunk
        if idx < len(chunks) - 1:
            body = {**body, "balance": None, "positions": None}
        r = requests.post(
            f"{cfg['server_url']}/api/ingest/mt5",
            json=body,
            headers={"Authorization": f"Bearer {auth.bearer()}"},
            timeout=60,
        )
        if r.status_code != 200:
            sys.exit(f"Ingest failed ({r.status_code}): {r.text[:400]}")
        s = r.json()
        print(
            f"  chunk {idx + 1}/{len(chunks)}: "
            f"+{s.get('raw_deals', 0)} deals, "
            f"{s.get('closed_trades', 0)} closed trades, "
            f"{s.get('open_positions', 0)} open positions"
        )


def sync_once(cfg: Dict[str, Any], auth: Auth) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[{stamp}] connecting to MT5 ...")
    mt5_connect(cfg)
    try:
        acc = mt5.account_info()
        account_id = f"MT5_{acc.login}"
        print(f"  account {acc.login} ({getattr(acc, 'company', '')}) -> {account_id}")
        cursor = get_cursor(cfg, auth, account_id)
        snapshot = read_snapshot(cursor)
        print(
            f"  read {len(snapshot['deals'])} new deal legs, "
            f"{len(snapshot['positions'])} open positions"
        )
        push(cfg, auth, snapshot)
        print("  done.")
    finally:
        mt5.shutdown()


def main() -> None:
    ap = argparse.ArgumentParser(description="TradeLogger MT5 push agent")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="one sync, then exit (default)")
    g.add_argument("--daemon", action="store_true", help="sync now, then loop forever")
    g.add_argument("--check", action="store_true", help="config + connectivity check only")
    args = ap.parse_args()

    cfg = load_config(args.config)
    auth = Auth(cfg)

    if args.check:
        print("config OK")
        print("auth ...", "OK" if auth.bearer() else "FAILED")
        mt5_connect(cfg)
        acc = mt5.account_info()
        print(f"MT5 OK -> account {acc.login} ({getattr(acc, 'company', '')})")
        mt5.shutdown()
        return

    if args.daemon:
        interval = max(60, int(cfg["poll_minutes"]) * 60)
        print(f"daemon mode: every {interval // 60} min. Ctrl+C to stop.")
        while True:
            try:
                sync_once(cfg, auth)
            except SystemExit as exc:
                print(f"  sync aborted: {exc}")
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                print(f"  unexpected error: {exc!r}")
            time.sleep(interval)
    else:
        sync_once(cfg, auth)


if __name__ == "__main__":
    main()
