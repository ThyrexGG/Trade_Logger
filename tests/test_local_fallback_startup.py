# -*- coding: utf-8 -*-
"""
Guard: the desktop app's local fallback (run_local_fallback.py) must come up fast.

2026-10-27 the cloud API was down and the desktop app never switched to local mode: its fallback.log showed
120 failed switches. The local server took ~94 s to answer /api/health (api/main.py's start-up warm-up requests
seven pages before uvicorn accepts a connection, and --sync-now ran one more blocking Capital.com + MT5 sync
first), and the app gives up and kills it at its start timeout. Skipping the warm-up and syncing in the
background brought it to ~3 s. These checks fail if either slow step comes back.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run_local_fallback.py").read_text(encoding="utf-8")
MAIN_JS = (ROOT / "desktop" / "main.js").read_text(encoding="utf-8")


def test_fallback_skips_the_startup_warmup_before_the_app_is_imported():
    skip = SCRIPT.index('os.environ.setdefault("TL_SKIP_WARMUP", "1")')
    assert skip < SCRIPT.index("from api.main import app"), "set TL_SKIP_WARMUP before api.main is imported"
    assert skip < SCRIPT.index("uvicorn.run("), "the warm-up runs inside uvicorn's start-up, so it must be skipped before serving"


def test_fallback_does_not_run_a_blocking_sync_before_serving():
    # the background loop (sync_service.set_auto) already syncs as soon as the server is up; a blocking
    # run_sync_cycle before uvicorn.run kept the page from opening, and could take minutes with no internet
    code = "\n".join(line for line in SCRIPT.splitlines() if not line.lstrip().startswith("#"))
    assert "run_sync_cycle" not in code
    assert "sync_service.set_auto(True)" in code


def test_the_app_waits_long_enough_for_the_fallback_to_start():
    ms = int(re.search(r"FALLBACK_START_TIMEOUT_MS\s*=\s*([\d_]+)", MAIN_JS).group(1).replace("_", ""))
    assert ms >= 120_000, "the app kills the fallback if it is not healthy by then; a slow PC needs room"
