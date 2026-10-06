#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temporary local fallback — run TradeLogger entirely on THIS PC when the cloud
backend (Render + Neon) is down.

This is the app's original single-user mode, still fully intact under the
multiuser/cloud layer: no login, its own local SQLite file
(``tradelogger_local_fallback.db``, next to this script), completely separate
from and never automatically synced with the cloud database. It's a
stand-in to keep working while the cloud is down, not a mirror of it.

Usage:
    python run_local_fallback.py [--sync-now] [--port 8010]

    --sync-now   Pull your real trade history into the local DB before
                 serving: Capital.com via the same CAPITAL_* credentials from
                 .env, and MT5 via this machine's own terminal (both talk
                 directly to the broker / MetaTrader -- neither goes through
                 Neon, so both work fine while the cloud DB is down).

Once serving, positions/closed trades keep refreshing on their own every
TL_SYNC_INTERVAL_SEC (default 60s here) via the same background sync loop
the cloud app uses -- so "live" positions/floating P&L stay live, not just a
one-time snapshot from --sync-now.

This one process serves BOTH the API and the built frontend (frontend/dist)
on the same port -- open http://127.0.0.1:8010 directly, no separate
`npx vite` needed. Run `npm run build` in frontend/ first (and again any
time you change the frontend and want the fallback to reflect it) --
frontend/dist is not rebuilt automatically.

Your MT5 sync agent (the scheduled task / --daemon) keeps talking to the
CLOUD server and is untouched by this — it'll just keep failing quietly
until the cloud is back, then catch up on its own. Nothing here changes it.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "tradelogger_local_fallback.db"

# --- neutralize load_dotenv(override=True) BEFORE anything else is imported ---
# database.py, capital_sync.py, mt5_sync.py, alerts.py all call
# load_dotenv(..., override=True) at their own import time, AND capital_sync.py /
# mt5_sync.py call it AGAIN every time their sync functions run -- so a one-time
# env correction gets silently undone the moment --sync-now (or later, a live
# "Sync now" click) triggers a real sync. Load the real .env ourselves once (so
# CAPITAL_* creds etc. are populated), then make every further load_dotenv call
# in this process a no-op, so our own overrides below are the last word for the
# rest of this process's life.
import dotenv  # noqa: E402

dotenv.load_dotenv(str(ROOT / ".env"))
dotenv.load_dotenv = lambda *a, **k: False

# Single-user, no-login, local-only -- exactly like the app worked before the
# cloud/multiuser layer existed (the same baseline tests/conftest.py uses: no
# TL_AUTH_PASSWORD/HASH configured means auth_enabled() is False on its own).
os.environ["TL_AUTH_MODE"] = "passphrase"
os.environ.pop("TL_AUTH_PASSWORD", None)
os.environ.pop("TL_AUTH_PASSWORD_HASH", None)
os.environ.pop("TL_AUTH_DISABLED", None)
os.environ["TL_PUSH_ENABLED"] = "0"  # no Firebase locally; desktop push isn't needed for this
os.environ["MT5_ENABLED"] = "1"      # safe here: this script only ever runs on a machine that may have MT5
# api/sync_service.py's default interval (900s / 15min) is tuned for Neon's compute-hour
# billing in the cloud -- this DB is local sqlite, so that cost doesn't exist here. A
# shorter interval keeps positions/closed trades genuinely live while this stands in.
os.environ.setdefault("TL_SYNC_INTERVAL_SEC", "60")


def _local_connect():
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=60000;")
    except Exception:
        pass
    return conn


def _pid_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ctypes.get_last_error() == 5  # access denied => exists
    try:
        code = ctypes.c_ulong()
        return bool(k32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
    finally:
        k32.CloseHandle(handle)


def _exit_when_parent_dies(pid: int) -> None:
    """The desktop app spawns this through a shell, and a force-closed or
    crashed app never runs its own cleanup -- either way this server used to
    outlive it as an orphan, holding port 8010 and polling MT5 indefinitely
    (one ran for 11+ hours, 2026-10-06). Watch the app's own PID instead of
    relying on being killed."""
    import threading
    import time

    def _watch() -> None:
        while _pid_alive(pid):
            time.sleep(5)
        print(f"Desktop app (pid {pid}) is gone -- shutting down the local fallback.", flush=True)
        os._exit(0)

    threading.Thread(target=_watch, name="parent-watch", daemon=True).start()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--sync-now", action="store_true", help="pull real Capital.com + MT5 history in before serving")
    ap.add_argument("--parent-pid", type=int, default=None,
                    help="exit as soon as this process (the desktop app) is gone")
    args = ap.parse_args()

    if args.parent_pid:
        _exit_when_parent_dies(args.parent_pid)

    import database
    database.get_db_url = lambda: None
    database.get_connection = _local_connect
    database.init_db(force=True)
    print(f"Local fallback DB: {DB_PATH}")
    print("Auth: disabled (single-user, this machine only -- do not port-forward this)")

    if args.sync_now:
        print("Syncing Capital.com + MT5 history into the local DB ...")
        import auto_sync
        # This runs unattended -- the desktop app starts it automatically when
        # the cloud fails two health checks -- so it must never be what opens a
        # MetaTrader you closed. A terminal that's already open still syncs.
        result = auto_sync.run_sync_cycle(set(), logfn=print, require_mt5_already_running=True)
        print(f"  done: {result.get('new_closed_trades', 0)} new closed trades, "
              f"capital_ok={result.get('capital_ok')}, mt5_ok={result.get('mt5_ok')}")

    # Keep positions/closed trades live for as long as this stands in for the cloud --
    # without this, sync only ever happened once (at --sync-now) and open positions /
    # floating P&L would silently go stale the whole time the cloud stayed down.
    import api.sync_service as sync_service
    sync_service.set_auto(True)
    print(f"Auto-sync: on, every {sync_service.INTERVAL_SEC}s")

    import uvicorn
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    from api.main import app

    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        # api/main.py already registers an exact GET / (a plain API-status JSON) --
        # Starlette matches routes in registration order, so that one would win over
        # any catch-all added after it, and "/" would never reach the SPA below.
        # Drop it here (in-process only, api/main.py itself is untouched) so index.html
        # is what actually loads at the site root, same as every other client route.
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/"]

        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="fallback-assets")

        @app.get("/{full_path:path}")
        async def _spa_fallback(full_path: str):  # noqa: ANN001
            # Reached only for paths no API route or /assets file matched. A genuine
            # unknown /api/* path stays a 404 instead of silently serving the SPA shell.
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            return FileResponse(str(dist / "index.html"))
    else:
        print(f"NOTE: {dist} not found -- run `npm run build` in frontend/ to serve the UI from here too.")

    print(f"\nServing on http://127.0.0.1:{args.port} -- open that directly in a browser.")
    print("Ctrl+C here to stop.\n")
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
