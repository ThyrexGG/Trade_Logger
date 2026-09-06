# -*- coding: utf-8 -*-
"""
System control router — the live-MT5 market-data switch.

Covers: GET returns the current state + the fail-closed safety barrier,
PUT persists and is reflected by market_data.is_live_market_data_enabled(),
the flag cache honours an explicit set, the MT5 branch in market_data is
gated by the flag (no terminal launch attempted when OFF), and POST is
rejected.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
import market_data

client = TestClient(app)


@pytest.fixture(autouse=True)
def _restore():
    original = market_data.is_live_market_data_enabled()
    yield
    market_data.set_live_market_data_enabled(original)


def test_get_reports_state_and_safety_barrier():
    r = client.get("/api/system/market-data")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["live_market_data_enabled"], bool)
    assert body["safety_barrier"] == {"live_automation_enabled": False,
                                      "live_broker_transmission": "BLOCKED"}


def test_put_persists_and_module_reflects_it():
    client.put("/api/system/market-data", json={"enabled": False})
    assert client.get("/api/system/market-data").json()["live_market_data_enabled"] is False
    assert market_data.is_live_market_data_enabled() is False

    client.put("/api/system/market-data", json={"enabled": True})
    assert market_data.is_live_market_data_enabled() is True


def test_flag_cache_updates_on_explicit_set():
    market_data.set_live_market_data_enabled(False)
    assert market_data.is_live_market_data_enabled() is False
    market_data.set_live_market_data_enabled(True)
    assert market_data.is_live_market_data_enabled() is True


def test_mt5_branch_is_gated_by_the_flag(monkeypatch):
    """With the switch OFF, get_realtime_candles must not even consult
    mt5_sync.MT5_AVAILABLE / MetaTrader5."""
    market_data.set_live_market_data_enabled(False)
    touched = {"mt5": False}

    class _FakeMT5Sync:
        @property
        def MT5_AVAILABLE(self):  # noqa: N802
            touched["mt5"] = True
            return True

    monkeypatch.setitem(__import__("sys").modules, "mt5_sync", _FakeMT5Sync())
    # should fall through to the non-MT5 fallbacks without raising
    market_data.get_realtime_candles("EURUSD", timeframe="1m", count=1, ttl_sec=0)
    assert touched["mt5"] is False


def test_account_state_short_circuits_when_switch_off():
    """account_state.get_account_state('MT5') must not call MetaTrader5 when
    the master switch is off — it launches the terminal."""
    import account_state
    market_data.set_live_market_data_enabled(False)
    state = account_state.get_account_state("MT5")
    assert "switched off" in (state.get("message") or "").lower()


def test_mt5_provider_connect_refuses_when_switch_off(monkeypatch):
    import mt5_provider
    market_data.set_live_market_data_enabled(False)
    called = {"init": False}
    monkeypatch.setattr(mt5_provider, "_available", lambda: True)
    if mt5_provider._mt5 is not None:
        monkeypatch.setattr(mt5_provider._mt5, "initialize",
                            lambda *a, **k: called.__setitem__("init", True) or True)
    assert mt5_provider._connect() is False
    assert called["init"] is False


def test_mt5_sync_skips_when_switch_off():
    import mt5_sync
    if not mt5_sync.MT5_AVAILABLE:
        return
    market_data.set_live_market_data_enabled(False)
    assert mt5_sync.sync_mt5() is False


def test_shared_gate_and_market_data_alias_agree():
    import mt5_gate
    market_data.set_live_market_data_enabled(False)
    assert mt5_gate.is_mt5_enabled() is False
    assert market_data.is_live_market_data_enabled() is False
    market_data.set_live_market_data_enabled(True)
    assert mt5_gate.is_mt5_enabled() is True


def test_post_is_rejected():
    assert client.post("/api/system/market-data").status_code == 405


# --- in-process broker-sync service -----------------------------------------
def test_sync_status_shape_and_safety_barrier():
    r = client.get("/api/system/sync")
    assert r.status_code == 200
    body = r.json()
    for k in ("auto_enabled", "loop_running", "cycle_in_progress", "interval_seconds"):
        assert k in body
    assert body["safety_barrier"] == {"live_automation_enabled": False,
                                      "live_broker_transmission": "BLOCKED"}


def test_sync_auto_toggle_persists(monkeypatch):
    from api import sync_service
    # don't actually spin the background thread in the test
    monkeypatch.setattr(sync_service, "_ensure_thread", lambda: None)
    try:
        client.put("/api/system/sync", json={"auto_enabled": True})
        assert client.get("/api/system/sync").json()["auto_enabled"] is True
        assert sync_service.is_auto_enabled() is True
    finally:
        client.put("/api/system/sync", json={"auto_enabled": False})
    assert sync_service.is_auto_enabled() is False


def test_sync_run_invokes_one_cycle(monkeypatch):
    from api import sync_service
    calls = {"n": 0}

    def _fake_cycle(known, logfn=None):
        calls["n"] += 1
        return {"errors": [], "mt5_ok": False, "capital_ok": True, "new_closed_trades": 0}

    monkeypatch.setattr(sync_service.auto_sync, "run_sync_cycle", _fake_cycle)
    r = client.post("/api/system/sync/run")
    assert r.status_code == 200
    body = r.json()
    assert calls["n"] == 1
    assert body["ran"]["ok"] is True and body["ran"]["capital_ok"] is True
    assert body["last_run"]["source"] == "manual"


def test_sync_service_imports_no_execution_layer():
    import inspect
    from api import sync_service
    src = inspect.getsource(sync_service)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway",
                "order_execution", "reconciliation"):
        assert bad not in src


def test_sync_endpoints_reject_wrong_verbs():
    assert client.get("/api/system/sync/run").status_code == 405
    assert client.delete("/api/system/sync").status_code == 405
