# -*- coding: utf-8 -*-
"""
W2 — the FastAPI backend must boot and serve without Streamlit (or plotly) installed.

The Streamlit terminal is retired (plan D1). `import api.main` used to pull
`streamlit` transitively via the watchlist / preferences / market / intelligence
routers. This runs the check in a subprocess with `streamlit` and `plotly`
blocked, so it neither depends on nor pollutes this process's module state.
"""
import subprocess
import sys
import textwrap


_SUBPROCESS = textwrap.dedent(
    """
    import importlib.abc, sys

    class _Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name.split(".")[0] in ("streamlit", "plotly"):
                raise ModuleNotFoundError("blocked in test: " + name)
            return None

    sys.meta_path.insert(0, _Block())
    for _m in [m for m in sys.modules if m.split(".")[0] in ("streamlit", "plotly")]:
        del sys.modules[_m]

    from fastapi.testclient import TestClient
    from api.main import app

    assert "streamlit" not in sys.modules, "something imported streamlit anyway"
    assert "plotly" not in sys.modules, "something imported plotly anyway"

    c = TestClient(app)
    checks = [
        "/api/health", "/api/watchlist", "/api/preferences",
        "/api/market/snapshot/XAUUSD", "/api/intelligence/summary", "/api/ai/status",
    ]
    for path in checks:
        r = c.get(path)
        assert r.status_code == 200, (path, r.status_code, r.text[:300])

    h = c.get("/api/health").json()
    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"
    print("OK")
    """
)


def test_backend_boots_and_serves_without_streamlit():
    proc = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    assert "OK" in proc.stdout


def test_watchlist_data_class_is_view_free():
    """The data methods the API calls must not touch the (now optional) `st`."""
    import trading_workspace_cockpit as twc

    rows = twc.TradingWorkspaceCockpit.get_watchlist_data(asset_filter="ALL")
    assert isinstance(rows, list) and rows
    assert all("symbol" in r and "price" in r for r in rows)


def test_requirements_txt_has_no_streamlit():
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    reqs = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "streamlit" not in reqs
    assert "plotly" not in reqs
    legacy = (root / "requirements-streamlit-legacy.txt").read_text(encoding="utf-8").lower()
    assert "streamlit" in legacy
