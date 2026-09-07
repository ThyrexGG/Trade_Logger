# -*- coding: utf-8 -*-
"""
System control router — the in-process broker-sync service — and the MT5
master gate.

The local MetaTrader 5 terminals were uninstalled, so the MT5 read paths are
OFF by default and opt-in only via the ``MT5_ENABLED`` env var (no UI, no DB
toggle). These tests cover: the gate defaults to OFF and the read-side MT5
branches are skipped, and the sync endpoints work + carry the fail-closed
safety barrier.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
import market_data
import mt5_gate

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_gate(monkeypatch):
    monkeypatch.delenv("MT5_ENABLED", raising=False)
    mt5_gate.clear_override()
    yield
    mt5_gate.clear_override()


# --- MT5 master gate -------------------------------------------------------
def test_gate_defaults_off():
    assert mt5_gate.is_mt5_enabled() is False
    assert market_data.is_live_market_data_enabled() is False


def test_gate_opts_in_via_env(monkeypatch):
    monkeypatch.setenv("MT5_ENABLED", "1")
    assert mt5_gate.is_mt5_enabled() is True
    monkeypatch.setenv("MT5_ENABLED", "0")
    assert mt5_gate.is_mt5_enabled() is False


def test_market_data_mt5_branch_is_skipped_when_off(monkeypatch):
    touched = {"mt5": False}

    class _FakeMT5Sync:
        @property
        def MT5_AVAILABLE(self):  # noqa: N802
            touched["mt5"] = True
            return True

    monkeypatch.setitem(__import__("sys").modules, "mt5_sync", _FakeMT5Sync())
    market_data.get_realtime_candles("EURUSD", timeframe="1m", count=1, ttl_sec=0)
    assert touched["mt5"] is False


def test_account_state_short_circuits_when_off():
    import account_state
    state = account_state.get_account_state("MT5")
    assert "switched off" in (state.get("message") or "").lower()


def test_mt5_provider_connect_refuses_when_off(monkeypatch):
    import mt5_provider
    called = {"init": False}
    monkeypatch.setattr(mt5_provider, "_available", lambda: True)
    if mt5_provider._mt5 is not None:
        monkeypatch.setattr(mt5_provider._mt5, "initialize",
                            lambda *a, **k: called.__setitem__("init", True) or True)
    assert mt5_provider._connect() is False
    assert called["init"] is False


# --- in-process broker-sync service -------------------------------------
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


def test_sync_run_if_stale_skips_when_fresh(monkeypatch):
    from api import sync_service

    calls = {"n": 0}

    def _fake_cycle(known, logfn=None):
        calls["n"] += 1
        return {"errors": [], "mt5_ok": False, "capital_ok": True, "new_closed_trades": 0}

    monkeypatch.setattr(sync_service.auto_sync, "run_sync_cycle", _fake_cycle)
    monkeypatch.setattr(sync_service, "is_auto_enabled", lambda: False)
    # heartbeat 2 minutes old -> a 15-minute window is still fresh
    monkeypatch.setattr(sync_service, "_heartbeat_age_sec", lambda: 120.0)

    body = client.post("/api/system/sync/run-if-stale?max_age_minutes=15").json()
    assert calls["n"] == 0
    assert body["skipped"] is True and body["reason"] == "fresh"


def test_sync_run_if_stale_runs_when_stale(monkeypatch):
    from api import sync_service

    calls = {"n": 0}

    def _fake_cycle(known, logfn=None):
        calls["n"] += 1
        return {"errors": [], "mt5_ok": False, "capital_ok": True, "new_closed_trades": 0}

    monkeypatch.setattr(sync_service.auto_sync, "run_sync_cycle", _fake_cycle)
    monkeypatch.setattr(sync_service, "is_auto_enabled", lambda: False)
    monkeypatch.setattr(sync_service, "_heartbeat_age_sec", lambda: 3600.0)  # 1h old

    body = client.post("/api/system/sync/run-if-stale?max_age_minutes=15").json()
    assert calls["n"] == 1
    assert body["ran"]["ok"] is True and body["ran"]["source"] == "open"


def test_sync_run_if_stale_defers_to_auto_loop(monkeypatch):
    from api import sync_service

    monkeypatch.setattr(sync_service, "is_auto_enabled", lambda: True)
    monkeypatch.setattr(
        sync_service.auto_sync, "run_sync_cycle",
        lambda *a, **k: pytest.fail("must not sync while the auto loop owns it"),
    )
    body = client.post("/api/system/sync/run-if-stale").json()
    assert body["skipped"] is True and body["reason"] == "auto_loop_on"


def test_sync_service_imports_no_execution_layer():
    import inspect
    from api import sync_service
    src = inspect.getsource(sync_service)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway",
                "order_execution", "reconciliation"):
        assert bad not in src


def test_market_data_toggle_endpoint_is_gone():
    assert client.get("/api/system/market-data").status_code == 404
    assert client.put("/api/system/market-data", json={"enabled": True}).status_code == 404


def test_sync_endpoints_reject_wrong_verbs():
    assert client.get("/api/system/sync/run").status_code == 405
    assert client.delete("/api/system/sync").status_code == 405
