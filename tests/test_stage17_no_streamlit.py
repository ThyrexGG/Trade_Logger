# -*- coding: utf-8 -*-
"""
W2 — the FastAPI backend must boot and serve without Streamlit installed.

The Streamlit terminal is retired (plan D1). `import api.main` used to pull
`streamlit` transitively via the watchlist / preferences / market / intelligence
routers. This test blocks `streamlit` from importing, then asserts the API still
comes up and the previously-tainted endpoints still answer.
"""
import importlib
import sys

import pytest


class _StreamlitBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "streamlit" or name.startswith("streamlit."):
            raise ModuleNotFoundError(f"streamlit is retired (blocked in test): {name}")
        return None


@pytest.fixture(scope="module")
def client_without_streamlit():
    blocker = _StreamlitBlocker()
    sys.meta_path.insert(0, blocker)
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] == "streamlit"}
    for k in saved:
        del sys.modules[k]
    # drop the modules that may have captured a real `streamlit` at import time
    for k in [m for m in sys.modules if m.split(".")[0] in {
        "api", "trading_workspace_cockpit", "user_preferences",
        "market_intelligence_command_center", "ui_components", "tradingview_widget",
        "workspace_layout_manager",
    }]:
        del sys.modules[k]
    try:
        from fastapi.testclient import TestClient

        api_main = importlib.import_module("api.main")
        assert "streamlit" not in sys.modules, "something imported streamlit anyway"
        yield TestClient(api_main.app)
    finally:
        try:
            sys.meta_path.remove(blocker)
        except ValueError:
            pass
        for k in [m for m in sys.modules if m.split(".")[0] in {
            "api", "trading_workspace_cockpit", "user_preferences",
            "market_intelligence_command_center",
        }]:
            del sys.modules[k]
        sys.modules.update(saved)


def test_api_main_imports_without_streamlit(client_without_streamlit):
    assert "streamlit" not in sys.modules


@pytest.mark.parametrize("path", [
    "/api/health",
    "/api/watchlist",
    "/api/preferences",
    "/api/market/snapshot/XAUUSD",
    "/api/intelligence/summary",
])
def test_previously_tainted_endpoints_still_answer(client_without_streamlit, path):
    r = client_without_streamlit.get(path)
    assert r.status_code == 200, r.text[:300]


def test_safety_invariants_hold_without_streamlit(client_without_streamlit):
    h = client_without_streamlit.get("/api/health").json()
    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"


def test_watchlist_data_class_is_view_free():
    """The data methods the API calls must not touch the (now optional) `st`."""
    import trading_workspace_cockpit as twc

    rows = twc.TradingWorkspaceCockpit.get_watchlist_data(asset_filter="ALL")
    assert isinstance(rows, list) and rows
    assert all("symbol" in r and "price" in r for r in rows)
