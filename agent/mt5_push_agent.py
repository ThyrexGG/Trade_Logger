#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradeLogger MT5 sync agent  (platform plan W9)
=============================================

Runs on YOUR Windows PC, next to your MetaTrader 5 terminal. It reads your
closed deals, open positions and balance from MT5 and sends them to
TradeLogger over HTTPS.

  * It never places, modifies or closes an order.
  * It only ever writes YOUR data (the server ties every row to your login).
  * It needs the MT5 terminal installed and logged in to the account you
    want to track.

Normal use: double-click the .exe once, type your TradeLogger email +
password. It installs a background task and keeps syncing every 15 minutes.

Command line:
    tradelogger-mt5-sync --setup      # the first-run wizard (also the default)
    tradelogger-mt5-sync --once       # one sync, then exit  (what the task runs)
    tradelogger-mt5-sync --daemon     # sync now, then loop  (Mac/Linux, or no task)
    tradelogger-mt5-sync --check      # verify login + MT5 connection only
    tradelogger-mt5-sync --uninstall  # remove the background task

Running from source instead of the .exe:  pip install MetaTrader5 requests
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover - present in the .exe and normal installs
    requests = None  # type: ignore

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore

AGENT_VERSION = "1.1.0"
TASK_NAME = "TradeLogger MT5 Sync"
HISTORY_FALLBACK_START = datetime(2020, 1, 1, tzinfo=timezone.utc)

# Public, non-secret default baked into the build so a friend only has to
# type their own email + password. A mt5_agent_config.json next to the
# program overrides any of these.
CONFIG_DEFAULTS: Dict[str, Any] = {
    "server_url": "https://tradelogger-api.onrender.com",
    "poll_minutes": 15,
}

_SAVE_KEYS = ("server_url", "email", "password", "passphrase", "poll_minutes")


# --------------------------------------------------------------------------- #
#  Paths + config
# --------------------------------------------------------------------------- #
def app_dir() -> Path:
    if getattr(sys, "frozen", False):          # PyInstaller one-file .exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def config_path() -> Path:
    return app_dir() / "mt5_agent_config.json"


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    cfg: Dict[str, Any] = dict(CONFIG_DEFAULTS)
    p = path or config_path()
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            sys.exit(f"{p.name} is not valid JSON: {exc}")
        cfg.update({k: v for k, v in raw.items() if not k.startswith("_")})
    cfg["server_url"] = str(cfg.get("server_url", "")).rstrip("/")
    try:
        cfg["poll_minutes"] = max(5, int(cfg.get("poll_minutes", 15)))
    except (TypeError, ValueError):
        cfg["poll_minutes"] = 15
    return cfg


def config_status(cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """(_complete_, _mode_). Mode is 'multiuser' or 'passphrase'."""
    if not cfg.get("server_url"):
        return False, ""
    if cfg.get("passphrase"):
        return True, "passphrase"
    if cfg.get("email") and cfg.get("password"):
        return True, "multiuser"
    return False, ""


def save_config(cfg: Dict[str, Any]) -> Path:
    out = config_path()
    data = {k: cfg[k] for k in _SAVE_KEYS if cfg.get(k) not in (None, "")}
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    return out


def _require_requests() -> None:
    if requests is None:
        sys.exit("The 'requests' package is missing. Run:  pip install requests")


def _msg(resp) -> str:
    """Human-readable error out of a FastAPI response body."""
    try:
        body = resp.json()
        return str(body.get("error") or body.get("detail") or resp.text)[:200]
    except Exception:
        return (resp.text or "")[:200]


# --------------------------------------------------------------------------- #
#  Auth  ->  a bearer token for the TradeLogger API
# --------------------------------------------------------------------------- #
class Auth:
    def __init__(self, cfg: Dict[str, Any]):
        _require_requests()
        self.cfg = cfg
        _, self._mode = config_status(cfg)
        self._token: Optional[str] = None
        # Sessions last ~30 days server-side; re-login well before then.
        self._expires_at = 0.0

    def bearer(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        self._login()
        return self._token or ""

    def _login(self) -> None:
        if self._mode == "multiuser":
            payload = {"email": self.cfg["email"], "password": self.cfg["password"]}
        else:
            payload = {"password": self.cfg["passphrase"]}
        r = requests.post(
            f"{self.cfg['server_url']}/api/auth/login", json=payload, timeout=20
        )
        if r.status_code in (401, 403):
            sys.exit(
                "TradeLogger login failed. Check your email and password"
                + (" (and that the owner has invited you)." if self._mode == "multiuser" else ".")
                + f"\n    (server said {r.status_code}: {_msg(r)})"
            )
        if r.status_code != 200:
            sys.exit(f"Login failed ({r.status_code}): {_msg(r)}")
        body = r.json()
        self._token = body.get("token")
        # server default TTL is 30 days; refresh conservatively every ~20h
        self._expires_at = time.time() + 20 * 3600
        if not self._token:
            sys.exit("Login response contained no session token.")


# --------------------------------------------------------------------------- #
#  MT5 read
# --------------------------------------------------------------------------- #
def _require_mt5() -> None:
    if mt5 is None:
        sys.exit(
            "The MetaTrader5 module is not available. Use the packaged .exe, or\n"
            "run:  pip install MetaTrader5   (Windows only)."
        )


def mt5_connect(cfg: Dict[str, Any]) -> None:
    _require_mt5()
    m = cfg.get("mt5") or {}
    login, password, server = m.get("login"), m.get("password"), m.get("server")
    ok = False
    if login and password and server:
        ok = mt5.initialize(login=int(login), password=str(password),
                            server=str(server), timeout=15000)
    if not ok:
        ok = mt5.initialize(timeout=15000)
    if not ok:
        sys.exit(
            f"Could not connect to MetaTrader 5 (error {mt5.last_error()}).\n"
            "    Open the MT5 terminal and log in to the account you want to track."
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
        positions.append({
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
        })

    start = (
        datetime.fromtimestamp(server_cursor_ts - 10, tz=timezone.utc)
        if server_cursor_ts > 0
        else HISTORY_FALLBACK_START
    )
    end = datetime.now(timezone.utc) + timedelta(days=2)

    deals = []
    for d in mt5.history_deals_get(start, end) or []:
        if d.type not in (0, 1):
            continue
        deals.append({
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
        })

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
def get_cursor(cfg: Dict[str, Any], auth: "Auth", account_id: str) -> int:
    r = requests.get(
        f"{cfg['server_url']}/api/ingest/mt5/cursor",
        params={"account": account_id},
        headers={"Authorization": f"Bearer {auth.bearer()}"},
        timeout=20,
    )
    if r.status_code == 401:
        sys.exit("Server rejected the login (401). Ask the owner to confirm your email is on the invite list.")
    if r.status_code != 200:
        print(f"  ! cursor lookup failed ({r.status_code}); doing a full history pull")
        return 0
    return int(r.json().get("last_deal_timestamp") or 0)


def push(cfg: Dict[str, Any], auth: "Auth", snapshot: Dict[str, Any]) -> None:
    payload = {k: v for k, v in snapshot.items() if not k.startswith("_")}
    deals = payload.pop("deals")
    chunk = 5000
    chunks = [deals[i:i + chunk] for i in range(0, len(deals), chunk)] or [[]]
    for idx, part in enumerate(chunks):
        body = {**payload, "deals": part}
        if idx < len(chunks) - 1:           # snapshot only on the final chunk
            body = {**body, "balance": None, "positions": None}
        r = requests.post(
            f"{cfg['server_url']}/api/ingest/mt5",
            json=body,
            headers={"Authorization": f"Bearer {auth.bearer()}"},
            timeout=60,
        )
        if r.status_code != 200:
            sys.exit(f"Upload failed ({r.status_code}): {r.text[:300]}")
        s = r.json()
        print(
            f"  chunk {idx + 1}/{len(chunks)}: +{s.get('raw_deals', 0)} deals, "
            f"{s.get('closed_trades', 0)} closed trades, "
            f"{s.get('open_positions', 0)} open positions"
        )


def sync_once(cfg: Dict[str, Any], auth: "Auth") -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[{stamp}] connecting to MetaTrader 5 ...")
    mt5_connect(cfg)
    try:
        acc = mt5.account_info()
        account_id = f"MT5_{acc.login}"
        print(f"  account {acc.login} ({getattr(acc, 'company', '')})")
        cursor = get_cursor(cfg, auth, account_id)
        snap = read_snapshot(cursor)
        print(f"  read {len(snap['deals'])} new deal legs, {len(snap['positions'])} open positions")
        push(cfg, auth, snap)
        print("  done.")
    finally:
        mt5.shutdown()


# --------------------------------------------------------------------------- #
#  Background task (Windows Task Scheduler, via a hidden VBS launcher)
# --------------------------------------------------------------------------- #
def _runner_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --once'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pyw) if pyw.exists() else sys.executable
    return f'"{exe}" "{Path(__file__).resolve()}" --once'


def _vbs_line(command: str) -> str:
    """A one-line VBS that runs `command` with no visible window."""
    return f'CreateObject("WScript.Shell").Run "{command.replace(chr(34), chr(34) * 2)}", 0, False\n'


def install_task(poll_minutes: int = 15) -> bool:
    if platform.system() != "Windows":
        print("  automatic scheduling is Windows-only — run with --daemon instead.")
        return False
    vbs = app_dir() / "mt5_sync_hidden.vbs"
    vbs.write_text(_vbs_line(_runner_command()), encoding="utf-8")
    res = subprocess.run(
        ["schtasks", "/Create", "/F", "/TN", TASK_NAME,
         "/SC", "MINUTE", "/MO", str(max(5, int(poll_minutes))),
         "/TR", f'wscript.exe "{vbs}"'],
        capture_output=True, text=True,
    )
    if res.returncode == 0:
        print(f"  background task '{TASK_NAME}' installed — syncs every {poll_minutes} min while this PC is on.")
        return True
    print("  could not install the background task:")
    print(f"    {(res.stderr or res.stdout).strip()}")
    print("  you can still sync by double-clicking this program.")
    return False


def uninstall_task() -> None:
    if platform.system() == "Windows":
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
                       capture_output=True, text=True)
    for f in ("mt5_sync_hidden.vbs",):
        try:
            (app_dir() / f).unlink()
        except OSError:
            pass
    print(f"  removed the background task '{TASK_NAME}'. Your synced data stays in TradeLogger.")


# --------------------------------------------------------------------------- #
#  First-run wizard
# --------------------------------------------------------------------------- #
_LOCK_STALE_SEC = 600


def _acquire_run_lock() -> Optional[Path]:
    """Stop the scheduled task from stacking: if a sync started less than
    ~10 min ago and hasn't cleared its lock, this run bows out."""
    lock = app_dir() / ".sync.lock"
    try:
        if lock.exists() and (time.time() - lock.stat().st_mtime) < _LOCK_STALE_SEC:
            return None
        lock.write_text(str(os.getpid()), encoding="utf-8")
        return lock
    except OSError:
        return lock  # can't manage the lock — proceed rather than stall


def _release_run_lock(lock: Optional[Path]) -> None:
    try:
        if lock is not None:
            lock.unlink()
    except OSError:
        pass


def _is_interactive() -> bool:
    """A real console (double-clicked or run from a terminal) vs the hidden
    scheduled task (launched by wscript with no console)."""
    try:
        return bool(sys.stdin and sys.stdin.isatty())
    except (ValueError, OSError):
        return False


def _pause_if_interactive() -> None:
    if not _is_interactive():
        return
    try:
        input("\nPress Enter to close.")
    except (EOFError, OSError):
        pass


def run_setup() -> None:
    print("=" * 60)
    print(" TradeLogger — connect your MetaTrader account")
    print("=" * 60)
    cfg = load_config()
    print("\nYou need the email and password you use to sign in to TradeLogger")
    print("(the same one the owner invited).\n")
    try:
        email = input("  TradeLogger email:    ").strip()
        password = getpass.getpass("  TradeLogger password: ").strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nCancelled.")
    if not email or not password:
        sys.exit("Both are required. Run the program again.")
    cfg["email"] = email
    cfg["password"] = password

    saved = save_config(cfg)
    print(f"\n  saved {saved.name}")

    print("  checking your TradeLogger login ...", end=" ", flush=True)
    auth = Auth(cfg)
    auth.bearer()
    print("OK")

    if mt5 is not None:
        print("  checking MetaTrader 5 connection ...", end=" ", flush=True)
        try:
            mt5_connect(cfg)
            acc = mt5.account_info()
            print(f"OK — account {acc.login} ({getattr(acc, 'company', '')})")
            mt5.shutdown()
        except SystemExit as exc:
            print("not ready")
            print(f"    {exc}")
            print("    Open MetaTrader 5 and log in; the next sync will pick it up.")
    else:
        print("  ! this build has no MetaTrader5 module — it cannot sync.")

    print()
    install_task(cfg["poll_minutes"])

    print("\n  running the first sync now ...")
    try:
        sync_once(cfg, auth)
    except SystemExit as exc:
        print(f"  first sync did not finish: {exc}")
        print("  it will retry automatically on the schedule.")

    print("\nAll set. Keep MetaTrader 5 running and logged in; TradeLogger updates itself.")


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #
def _dispatch(args: argparse.Namespace) -> None:
    if args.uninstall:
        uninstall_task()
        return

    cfg = load_config(args.config)
    complete, _mode = config_status(cfg)

    # A bare double-click: run the wizard if not set up yet, else sync once.
    if args.setup or (not any((args.once, args.daemon, args.check)) and not complete):
        run_setup()
        return

    if not complete:
        sys.exit("Not configured yet. Run the program with no arguments to set it up.")

    auth = Auth(cfg)

    if args.check:
        print("config: OK")
        print("login :", "OK" if auth.bearer() else "FAILED")
        mt5_connect(cfg)
        acc = mt5.account_info()
        print(f"MT5   : OK — account {acc.login} ({getattr(acc, 'company', '')})")
        mt5.shutdown()
        return

    if args.daemon:
        interval = cfg["poll_minutes"] * 60
        print(f"daemon: syncing every {cfg['poll_minutes']} min. Ctrl+C to stop.")
        while True:
            try:
                sync_once(cfg, auth)
            except SystemExit as exc:
                print(f"  sync aborted: {exc}")
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                print(f"  unexpected error: {exc!r}")
            time.sleep(interval)
        return

    # --once  (also what the scheduled task runs)
    lock = _acquire_run_lock()
    if lock is None:
        print("another sync is already running — skipping.")
        return
    try:
        sync_once(cfg, auth)
    except SystemExit as exc:
        print(f"sync did not finish: {exc}")
        raise SystemExit(1) from None
    finally:
        _release_run_lock(lock)


def main() -> None:
    ap = argparse.ArgumentParser(description="TradeLogger MT5 sync agent", add_help=True)
    ap.add_argument("--config", type=Path, default=None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--setup", action="store_true", help="first-run wizard (default on a fresh install)")
    g.add_argument("--once", action="store_true", help="one sync, then exit")
    g.add_argument("--daemon", action="store_true", help="sync now, then loop forever")
    g.add_argument("--check", action="store_true", help="verify login + MT5 connection only")
    g.add_argument("--uninstall", action="store_true", help="remove the background task")
    args = ap.parse_args()

    # Whatever happens — success, a handled error, or an unexpected crash — a
    # double-clicked window must stay open long enough to read the message.
    # The hidden scheduled task (no console) is unaffected.
    try:
        _dispatch(args)
    except SystemExit as exc:
        if isinstance(exc.code, str):     # sys.exit("message")
            print(exc.code)
        _pause_if_interactive()
        raise SystemExit(exc.code if isinstance(exc.code, int) else (0 if not exc.code else 1))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 - last-resort so the window doesn't vanish
        print(f"\nUnexpected error: {exc!r}")
        _pause_if_interactive()
        raise SystemExit(1)
    _pause_if_interactive()


if __name__ == "__main__":
    main()
