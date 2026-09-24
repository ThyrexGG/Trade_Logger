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
password. It installs a background task that syncs every 15 minutes WHILE
MetaTrader 5 is open — closing MT5 (no more trades to catch) just makes it
skip that run instead of reopening the terminal for you.

Run it with --daemon instead (e.g. while you're actively trading) and it
syncs every 30 seconds by default, and the moment it sees a trade close --
a position that had deals last sync and doesn't anymore -- it pops a
Windows toast and opens your browser straight to that trade's journal
entry, ready to fill in. Both the interval and this behaviour are
config-file overrides (daemon_poll_seconds, notify_on_close, web_url) --
see mt5_agent_config.example.json. It's best-effort: it never blocks or
fails a sync if the notification itself doesn't fire.

Command line:
    tradelogger-mt5-sync --setup      # the first-run wizard (also the default)
    tradelogger-mt5-sync --once       # one sync, then exit  (what the task runs)
    tradelogger-mt5-sync --daemon     # sync now, then loop fast, with notifications
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
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover - present in the .exe and normal installs
    requests = None  # type: ignore

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore

# Every helper process this agent shells out to (tasklist, schtasks, taskkill, powershell) is invoked
# from pythonw.exe, which has no console of its own -- without this flag Windows allocates a brand new
# console window for each one, which flashes on screen (and can steal focus from whatever's fullscreen)
# for the instant it takes the command to run. getattr() because the constant only exists on Windows.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

AGENT_VERSION = "1.3.0"
TASK_NAME = "TradeLogger MT5 Sync"
HISTORY_FALLBACK_START = datetime(2020, 1, 1, tzinfo=timezone.utc)

# Public, non-secret default baked into the build so a friend only has to
# type their own email + password. A mt5_agent_config.json next to the
# program overrides any of these.
CONFIG_DEFAULTS: Dict[str, Any] = {
    "server_url": "https://tradelogger-api.onrender.com",
    "poll_minutes": 15,
    # Only used in --daemon mode; the scheduled task still runs on
    # poll_minutes. 15 min was fine for a background catch-up task, but
    # useless if the point is seeing a closed trade land "instantly" while
    # you're actually watching -- so daemon mode gets its own, much shorter,
    # independently-configurable interval.
    "daemon_poll_seconds": 30,
    # Where the web app itself lives (NOT the API host in server_url) --
    # used only to build the "open the journal for this trade" link.
    "web_url": "https://tradelogger.site",
    # Best-effort Windows toast + auto-opened journal tab the moment a new
    # closed trade is detected. Off switch for anyone who finds it noisy.
    "notify_on_close": True,
}

_SAVE_KEYS = (
    "server_url", "email", "password", "passphrase", "poll_minutes",
    "daemon_poll_seconds", "web_url", "notify_on_close",
)


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
    cfg["web_url"] = str(cfg.get("web_url") or CONFIG_DEFAULTS["web_url"]).rstrip("/")
    try:
        cfg["poll_minutes"] = max(5, int(cfg.get("poll_minutes", 15)))
    except (TypeError, ValueError):
        cfg["poll_minutes"] = 15
    try:
        # Floor of 10s: MT5's own reconnect/history pull has real latency,
        # and hammering it faster than that just burns CPU for no benefit.
        cfg["daemon_poll_seconds"] = max(10, int(cfg.get("daemon_poll_seconds", 30)))
    except (TypeError, ValueError):
        cfg["daemon_poll_seconds"] = 30
    cfg["notify_on_close"] = bool(cfg.get("notify_on_close", True))
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


def _mt5_pids() -> Optional[set]:
    """PIDs of any running MT5 terminal process, or None if that couldn't be
    checked. Every white-labelled MT5 build (broker re-skins, prop-firm
    terminals, ...) still ships MetaQuotes' actual binary under the hood, so
    matching the two real process names catches effectively everyone
    regardless of the Start Menu shortcut's branding."""
    if platform.system() != "Windows":
        return None
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        ).stdout
    except Exception:
        return None
    pids: set = set()
    for line in out.splitlines():
        line = line.strip()
        if not (line.startswith('"') and line.endswith('"')):
            continue
        parts = line[1:-1].split('","')
        if len(parts) >= 2 and parts[0].lower() in ("terminal64.exe", "terminal.exe"):
            try:
                pids.add(int(parts[1]))
            except ValueError:
                pass
    return pids


def _minimize_windows_for_pids(pids: set) -> None:
    """Best-effort: minimize (never close) any visible window belonging to
    one of these process ids. Only ever called with PIDs WE just launched —
    a terminal the user already had open is never touched."""
    if not pids:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_MINIMIZE = 6

        def _pid_of(hwnd) -> int:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd) and _pid_of(hwnd) in pids:
                user32.ShowWindow(hwnd, SW_MINIMIZE)
            return True

        user32.EnumWindows(_enum, 0)
    except Exception:
        pass  # cosmetic only -- never let this get in the way of a sync


def _watch_and_minimize_new_terminal(before_pids: set, stop: threading.Event) -> None:
    """Runs on a background thread for the few seconds `mt5.initialize()`
    spends cold-launching a terminal (splash screen, then the main window) —
    polls for a newly-appeared MT5 process and minimizes it the moment it's
    visible, instead of waiting for initialize() to return and only then
    doing it once, by which point the window has already sat in the user's
    face for however long the cold start took."""
    deadline = time.time() + 25
    while not stop.is_set() and time.time() < deadline:
        pids = _mt5_pids()
        if pids:
            new = pids - before_pids
            if new:
                _minimize_windows_for_pids(new)
        stop.wait(0.3)


def mt5_connect(cfg: Dict[str, Any]) -> None:
    _require_mt5()
    # If nothing is running yet, mt5.initialize() below will launch a fresh
    # terminal itself. The automatic sync paths (--once / --daemon) never
    # reach this with MT5 closed -- sync_once()'s require_already_running
    # guard skips the sync before calling here -- so this only fires for an
    # explicit manual action (--check, the wizard's own first sync), where
    # launching it makes sense. What it shouldn't do either way is plant that
    # window in front of whatever the user is doing. A background thread watches
    # for the new process for as long as initialize() is busy connecting to
    # it and minimizes it the moment it appears; a terminal that was already
    # open (before_pids non-empty) is never touched.
    before_pids = _mt5_pids() or set()
    stop = None
    watcher = None
    if platform.system() == "Windows":
        stop = threading.Event()
        watcher = threading.Thread(
            target=_watch_and_minimize_new_terminal, args=(before_pids, stop), daemon=True,
        )
        watcher.start()

    try:
        m = cfg.get("mt5") or {}
        login, password, server = m.get("login"), m.get("password"), m.get("server")
        ok = False
        if login and password and server:
            ok = mt5.initialize(login=int(login), password=str(password),
                                server=str(server), timeout=15000)
        if not ok:
            ok = mt5.initialize(timeout=15000)
    finally:
        if stop is not None:
            stop.set()
        if watcher is not None:
            watcher.join(timeout=2)

    if not ok:
        sys.exit(
            f"Could not connect to MetaTrader 5 (error {mt5.last_error()}).\n"
            "    Open the MT5 terminal and log in to the account you want to track."
        )

    # Catch the gap between the watcher's last poll and initialize() returning.
    after_pids = _mt5_pids()
    if after_pids:
        _minimize_windows_for_pids(after_pids - before_pids)


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
    open_tickets = set()
    for p in mt5.positions_get() or []:
        open_tickets.add(str(p.ticket))
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

    # Which of this batch's positions are now fully closed, for the desktop
    # notification -- worked out locally rather than trusting the server's
    # closed-trade count, which is a plain integer with no identity in it.
    # A position_id that shows up in these new deals but ISN'T in the
    # account's currently-open positions has closed since the last sync.
    # Skipped entirely on the very first-ever sync (server_cursor_ts == 0,
    # a full-history backfill) -- otherwise every trade the account has ever
    # closed would fire a notification in one burst.
    closing_events: List[Dict[str, Any]] = []
    if server_cursor_ts > 0:
        by_position: Dict[str, List[Dict[str, Any]]] = {}
        for d in deals:
            by_position.setdefault(d["position_id"], []).append(d)
        for pos_id, legs in by_position.items():
            if pos_id in open_tickets:
                continue  # still open -- not a close
            legs.sort(key=lambda d: d["timestamp"])
            closing_events.append({
                "position_id": pos_id,
                "symbol": legs[0]["symbol"],
                "direction": legs[0]["type"],
                "volume": legs[-1]["volume"],
                "net_profit": sum(d["profit"] + d["commission"] + d["swap"] for d in legs),
                "closed_at": legs[-1]["timestamp"],
            })

    return {
        "account_id": account_id,
        "agent_version": AGENT_VERSION,
        "balance": balance,
        "positions": positions,
        "deals": deals,
        "_login": acc.login,
        "_company": getattr(acc, "company", ""),
        "_closing_events": closing_events,
    }


# --------------------------------------------------------------------------- #
#  Sync
# --------------------------------------------------------------------------- #
def get_cursor(cfg: Dict[str, Any], auth: "Auth", account_id: str) -> int:
    delay = 3
    r = None
    for attempt in range(1, 6):
        try:
            r = requests.get(
                f"{cfg['server_url']}/api/ingest/mt5/cursor",
                params={"account": account_id},
                headers={"Authorization": f"Bearer {auth.bearer()}"},
                timeout=60,
            )
        except requests.RequestException:
            r = None
        if r is not None and r.status_code == 401:
            sys.exit("Server rejected the login (401). Ask the owner to confirm your email is on the invite list.")
        if r is not None and r.status_code == 200:
            return int(r.json().get("last_deal_timestamp") or 0)
        if attempt < 5:
            print(f"  waking the server (attempt {attempt}/5); retry in {delay}s")
            time.sleep(delay)
            delay = min(delay * 2, 30)
    code = r.status_code if r is not None else "no response"
    print(f"  ! cursor lookup failed ({code}); doing a full history pull")
    return 0


#: legs per POST. Small on purpose — the server runs on a 512 MB free tier
#: and a fresh account can have thousands of legs of back-history. A big
#: batch there is a gateway 502, not a faster sync.
PUSH_CHUNK = 400
#: transient upstream states worth retrying (Render cold-start / brief 502)
_RETRY_CODES = {429, 500, 502, 503, 504}


def _post_chunk(cfg: Dict[str, Any], auth: "Auth", body: Dict[str, Any]) -> "requests.Response":
    """POST one chunk, retrying a few times on a cold-start / gateway blip."""
    delay = 3
    for attempt in range(1, 6):
        try:
            r = requests.post(
                f"{cfg['server_url']}/api/ingest/mt5",
                json=body,
                headers={"Authorization": f"Bearer {auth.bearer()}"},
                timeout=120,
            )
        except requests.RequestException as exc:
            if attempt == 5:
                raise
            print(f"  network error ({exc.__class__.__name__}); retry in {delay}s")
            time.sleep(delay)
            delay = min(delay * 2, 30)
            continue
        if r.status_code in _RETRY_CODES and attempt < 5:
            print(f"  server busy ({r.status_code}); retry in {delay}s "
                  f"(attempt {attempt}/5)")
            time.sleep(delay)
            delay = min(delay * 2, 30)
            continue
        return r
    return r


def push(cfg: Dict[str, Any], auth: "Auth", snapshot: Dict[str, Any]) -> None:
    payload = {k: v for k, v in snapshot.items() if not k.startswith("_")}
    deals = payload.pop("deals")
    chunks = [deals[i:i + PUSH_CHUNK] for i in range(0, len(deals), PUSH_CHUNK)] or [[]]
    total = len(chunks)
    for idx, part in enumerate(chunks):
        body = {**payload, "deals": part}
        if idx < total - 1:                  # snapshot only on the final chunk
            body = {**body, "balance": None, "positions": None}
        r = _post_chunk(cfg, auth, body)
        if r.status_code != 200:
            sys.exit(f"Upload failed ({r.status_code}): {r.text[:300]}")
        s = r.json()
        print(
            f"  chunk {idx + 1}/{total}: +{s.get('raw_deals', 0)} deals, "
            f"{s.get('closed_trades', 0)} closed trades, "
            f"{s.get('open_positions', 0)} open positions"
        )


def _toast(title: str, body: str) -> None:
    """Best-effort Windows toast. Never raises -- a notification failing is
    not a sync failing, and this has to survive machines with no
    powershell.exe on PATH, a locked-down notification policy, or a
    non-Windows OS (the .exe is Windows-only, but `--daemon` from source
    isn't restricted to it)."""
    if platform.system() != "Windows":
        return
    # Raw WinRT toast via PowerShell -- no BurntToast module install needed.
    # Runs under powershell.exe's own AUMID, which is why the click action
    # below opens a URL directly rather than relying on toast activation
    # routing back into this program.
    ps = f"""
$ErrorActionPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(2)
$textNodes = $xml.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($xml.CreateTextNode("{title}")) | Out-Null
$textNodes.Item(1).AppendChild($xml.CreateTextNode("{body}")) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("TradeLogger").Show($toast)
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
    except Exception:
        pass  # notification is a nicety, not the job


def _notify_closing_events(cfg: Dict[str, Any], events: List[Dict[str, Any]]) -> None:
    """Toast + auto-opened journal tab for trades that closed since the last
    sync. `notify_on_close: false` in the config turns this off entirely."""
    if not events or not cfg.get("notify_on_close", True):
        return
    web = cfg["web_url"]
    if len(events) == 1:
        e = events[0]
        sign = "+" if e["net_profit"] >= 0 else "-"
        body = f"{e['symbol']} {e['direction']} closed  {sign}${abs(e['net_profit']):.2f}"
        journal_url = f"{web}/workspace/journal?trade={e['position_id']}"
    else:
        total = sum(e["net_profit"] for e in events)
        sign = "+" if total >= 0 else "-"
        body = f"{len(events)} trades closed  ·  net {sign}${abs(total):.2f}"
        journal_url = f"{web}/workspace/journal"
    _toast("TradeLogger", body + " -- opening the journal to log it")
    try:
        import webbrowser
        webbrowser.open(journal_url)
    except Exception:
        pass  # the toast still told them; a browser window is a nicety


def sync_once(cfg: Dict[str, Any], auth: "Auth", require_already_running: bool = False) -> None:
    """`require_already_running=True` is what the automatic paths (the 15-min
    scheduled task and `--daemon`) pass: if MetaTrader isn't open, this skips
    the sync instead of `mt5_connect()`'s normal behaviour of launching a
    fresh terminal. The point of the schedule is "sync while I'm trading" —
    closing MT5 (no more trades to catch) shouldn't make it pop back up every
    15 minutes. A manual `--check` or the wizard's own first sync still want
    the old launch-it-for-me behaviour, so they leave this False."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    if require_already_running and not _mt5_pids():
        print(f"[{stamp}] MetaTrader 5 isn't open — skipping this sync (nothing to catch).")
        return
    print(f"[{stamp}] connecting to MetaTrader 5 ...")
    mt5_connect(cfg)
    try:
        acc = mt5.account_info()
        account_id = f"MT5_{acc.login}"
        print(f"  account {acc.login} ({getattr(acc, 'company', '')})")
        cursor = get_cursor(cfg, auth, account_id)
        snap = read_snapshot(cursor)
        print(f"  read {len(snap['deals'])} new deal legs, {len(snap['positions'])} open positions")
        closing_events = snap.get("_closing_events") or []
        push(cfg, auth, snap)
        if closing_events:
            print(f"  {len(closing_events)} trade(s) closed since last sync -- notifying")
            _notify_closing_events(cfg, closing_events)
        print("  done.")
    finally:
        mt5.shutdown()


# --------------------------------------------------------------------------- #
#  Background task (Windows Task Scheduler, via a hidden VBS launcher)
# --------------------------------------------------------------------------- #
def _self_invocation() -> str:
    """Quoted "how to run this exact program again" prefix, shared by the
    hidden scheduled-task launcher and the double-clickable Uninstall.bat."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def _runner_command() -> str:
    if getattr(sys, "frozen", False):
        return f"{_self_invocation()} --once"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pyw) if pyw.exists() else sys.executable
    return f'"{exe}" "{Path(__file__).resolve()}" --once'


def _vbs_line(command: str) -> str:
    """A one-line VBS that runs `command` with no visible window."""
    return f'CreateObject("WScript.Shell").Run "{command.replace(chr(34), chr(34) * 2)}", 0, False\n'


UNINSTALL_BAT_NAME = "Uninstall TradeLogger Sync.bat"


def write_uninstall_shortcut() -> Path:
    """A literal, double-clickable file sitting right next to the program —
    no command line, no CLI flag to remember, no digging through Task
    Scheduler. `--uninstall` always existed but only as a terminal argument,
    which is no help to someone who doesn't know what a terminal is; this is
    the actual fix for that. Rewritten idempotently on every setup and every
    sync so an install made before this existed self-heals without anyone
    re-running the wizard."""
    bat = app_dir() / UNINSTALL_BAT_NAME
    content = (
        "@echo off\r\n"
        "echo Removing the TradeLogger background sync...\r\n"
        f"{_self_invocation()} --uninstall\r\n"
        "echo.\r\n"
        "pause\r\n"
    )
    try:
        if not bat.exists() or bat.read_text(encoding="utf-8", errors="ignore") != content:
            bat.write_text(content, encoding="utf-8")
    except OSError:
        pass  # not load-bearing -- --uninstall from a terminal still works
    return bat


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
        creationflags=_NO_WINDOW,
    )
    if res.returncode == 0:
        write_uninstall_shortcut()
        print(f"  background task '{TASK_NAME}' installed — syncs every {poll_minutes} min while this PC is on.")
        print(f"  to remove it later, double-click '{UNINSTALL_BAT_NAME}' in this folder.")
        return True
    print("  could not install the background task:")
    print(f"    {(res.stderr or res.stdout).strip()}")
    print("  you can still sync by double-clicking this program.")
    return False


def uninstall_task() -> None:
    if platform.system() != "Windows":
        print("  nothing to remove (no background task on this OS).")
        return

    # 1. delete the scheduled task — and actually check it worked
    res = subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
                         capture_output=True, text=True, creationflags=_NO_WINDOW)
    out = (res.stderr or res.stdout or "").strip()
    if res.returncode == 0:
        print(f"  removed the scheduled task '{TASK_NAME}'.")
    elif "cannot find" in out.lower() or "does not exist" in out.lower():
        print(f"  scheduled task '{TASK_NAME}' was already gone.")
    else:
        print(f"  ! could not delete the scheduled task: {out}")
        print("    open Task Scheduler, find 'TradeLogger MT5 Sync', right-click -> Delete.")

    # 2. stop any OTHER copy still running (a stuck sync would relaunch MT5
    #    once more) — never this process, or we'd die before finishing
    if getattr(sys, "frozen", False):
        subprocess.run(
            ["taskkill", "/F", "/IM", Path(sys.executable).name,
             "/FI", f"PID ne {os.getpid()}"],
            capture_output=True, text=True,
            creationflags=_NO_WINDOW,
        )

    # 3. remove the hidden launcher, the uninstall shortcut, and stale lock
    for f in ("mt5_sync_hidden.vbs", ".sync.lock", UNINSTALL_BAT_NAME):
        try:
            (app_dir() / f).unlink()
        except OSError:
            pass

    # 4. confirm
    check = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME],
                           capture_output=True, text=True, creationflags=_NO_WINDOW)
    if check.returncode != 0:
        print("  confirmed: the task is gone. MetaTrader 5 will not be reopened anymore.")
        print("  (your trades already in TradeLogger stay. you can delete this folder.)")
    else:
        print("  ! the task still shows in Task Scheduler — remove it there manually.")


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
    """A real, visible console (double-clicked or run from a terminal) vs
    the hidden scheduled task (launched by wscript with its window style
    set to 0/hidden).

    `sys.stdin.isatty()` alone is NOT enough here: `wscript.exe ...
    Run(cmd, 0, False)` still attaches a real console to the child process
    -- it's just invisible -- so isatty() reports True for it exactly the
    same as a console the user can actually see and type into. Relying on
    isatty() alone made every single scheduled run call `input()` below and
    block forever waiting for a keypress nobody could ever send, which is
    what stacked ~150 zombie processes (and ~6 GB of leaked PyInstaller
    temp folders, one per run) over about 19 hours before this was caught.
    Checking the console window's actual visibility via the Win32 API is
    what a hidden launch and a real one don't share."""
    try:
        if not (sys.stdin and sys.stdin.isatty()):
            return False
    except (ValueError, OSError):
        return False

    if platform.system() != "Windows":
        return True  # isatty() is a reliable signal on Mac/Linux

    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        return bool(hwnd) and bool(ctypes.windll.user32.IsWindowVisible(hwnd))
    except Exception:
        # Can't tell -- assume hidden/non-interactive. A missed "press enter"
        # pause (window closes a beat early) is far cheaper than another
        # process hanging forever on stdin that will never arrive.
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

    # Self-heal: an install made before Uninstall.bat existed gets one here,
    # on its next ordinary run, without anyone having to redo the wizard.
    if platform.system() == "Windows":
        write_uninstall_shortcut()

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
        interval = cfg["daemon_poll_seconds"]
        print(f"daemon: syncing every {interval}s. Ctrl+C to stop.")
        while True:
            try:
                sync_once(cfg, auth, require_already_running=True)
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
        sync_once(cfg, auth, require_already_running=True)
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
    g.add_argument("--daemon", action="store_true", help="sync now, then loop fast (with close notifications)")
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
