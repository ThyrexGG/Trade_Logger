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


def test_post_is_rejected():
    assert client.post("/api/system/market-data").status_code == 405
