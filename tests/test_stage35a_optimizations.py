# -*- coding: utf-8 -*-
"""
Tests for Stage 3.5A High-Impact API Latency Optimizations
==========================================================
Verifies:
1. /api/market/snapshot/{symbol}: single-symbol path does NOT invoke get_watchlist_data("ALL").
2. /api/preferences: process-level cache returns correct values without DB queries on repeated GETs,
   and PUT updates / invalidates cache correctly.
3. /api/positions: short TTL (2.0s) caching is respected and refreshes after expiry.
4. Response schemas for all three endpoints remain 100% compliant and intact.
"""
import time
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from user_preferences import UserPreferencesManager
from trading_workspace_cockpit import TradingWorkspaceCockpit
import database

client = TestClient(app)


def test_market_snapshot_single_symbol_bypass():
    """Verify get_market_snapshot does NOT call get_watchlist_data('ALL')."""
    with patch.object(TradingWorkspaceCockpit, "get_watchlist_data", side_effect=AssertionError("get_watchlist_data('ALL') was unexpectedly called!")):
        response = client.get("/api/market/snapshot/XAUUSD")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "XAUUSD"
        assert data["display"] == "XAUUSD"
        assert "price" in data
        assert "mtf_bias" in data
        assert "1D" in data["mtf_bias"]
        assert data["live_broker_transmission"] == "BLOCKED"


def test_preferences_process_cache_and_put_invalidation():
    """Verify process-level cache serves GETs and PUT correctly invalidates/updates."""
    # Warm up cache
    UserPreferencesManager.initialize_preferences(force_reload=True)

    # First GET
    res1 = client.get("/api/preferences")
    assert res1.status_code == 200
    p1 = res1.json()["preferences"]

    # During subsequent GETs, no DB connection should be needed
    with patch("database.get_connection", side_effect=AssertionError("database.get_connection was called during cached GET!")):
        res2 = client.get("/api/preferences")
        assert res2.status_code == 200
        assert res2.json()["preferences"]["selected_asset"] == p1["selected_asset"]

    # PUT update
    update_res = client.put("/api/preferences", json={"active_workspace_layout": "RESEARCH"})
    assert update_res.status_code == 200
    assert update_res.json()["preferences"]["active_workspace_layout"] == "RESEARCH"

    # Immediate GET reflects update
    res3 = client.get("/api/preferences")
    assert res3.json()["preferences"]["active_workspace_layout"] == "RESEARCH"

    # Restore default
    client.put("/api/preferences", json={"active_workspace_layout": "DEFAULT"})


def test_positions_short_ttl_caching_and_refresh():
    """Verify that positions endpoint uses 2.0s TTL caching and refreshes on expiry."""
    # First call warms cache
    res1 = client.get("/api/positions")
    assert res1.status_code == 200
    data1 = res1.json()

    # Immediate second call should use cache without connecting to DB
    with patch("database.get_connection", side_effect=AssertionError("database.get_connection called during cached positions TTL!")):
        res2 = client.get("/api/positions")
        assert res2.status_code == 200
        assert res2.json()["total_open"] == data1["total_open"]

    # Wait for TTL to expire (2.1s)
    time.sleep(2.1)

    # Call after expiry reconnects to DB cleanly
    res3 = client.get("/api/positions")
    assert res3.status_code == 200
    assert "positions" in res3.json()


def test_api_response_schemas_unchanged():
    """Verify schema integrity of snapshot, preferences, and positions."""
    snap = client.get("/api/market/snapshot/USDJPY").json()
    assert set(snap.keys()) == {
        "symbol", "display", "price", "bid", "ask", "spread",
        "session", "mtf_bias", "setup_state", "edge_score",
        "macro_score", "data_quality", "live_broker_transmission",
        "cached", "timestamp"
    }

    prefs = client.get("/api/preferences").json()
    assert "preferences" in prefs
    assert "updated_at" in prefs
    assert set(prefs["preferences"].keys()) == {
        "selected_asset", "selected_timeframe", "active_workspace_layout",
        "watchlist_filter", "compact_mode", "shortcuts_enabled",
        "last_active_zone", "last_active_subtab"
    }

    pos = client.get("/api/positions").json()
    assert "positions" in pos
    assert "total_open" in pos
    assert "total_floating_pnl" in pos
    assert "timestamp" in pos
