# -*- coding: utf-8 -*-
"""
Phase 63 / Stage 2 Migration Test Suite — FastAPI Read-Only Foundation & Semantic Parity Verification
=====================================================================================================
Verifies:
1. /api/health: Lightweight process status and fail-closed safety gate configuration.
2. /api/watchlist: Semantic parity against authoritative TradingWorkspaceCockpit.get_watchlist_data().
3. /api/market/snapshot/{symbol}: Semantic parity against TradingWorkspaceCockpit.get_mtf_bias_hierarchy().
4. Read-Only Boundary: Prohibits write mutations and confirms live transmission is blocked.
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app
from trading_workspace_cockpit import TradingWorkspaceCockpit, WATCHLIST_SYMBOLS
import market_data

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. Health Endpoint Tests
# -----------------------------------------------------------------------------
def test_api_health_lightweight_response():
    """Verify /api/health returns fast 200 OK with fail-closed safety constants."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["app_name"] == "TradeLogger Fast Terminal API"
    assert data["version"] == "2.0.0"
    assert data["live_broker_transmission"] == "BLOCKED"
    assert data["automation_enabled"] is False
    assert "timestamp" in data


# -----------------------------------------------------------------------------
# 2. Watchlist Endpoint & Semantic Parity Tests
# -----------------------------------------------------------------------------
def test_api_watchlist_semantic_parity_all():
    """Verify /api/watchlist matches authoritative Python engine data exactly."""
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    api_payload = response.json()

    # Authoritative Python engine call
    engine_data = TradingWorkspaceCockpit.get_watchlist_data("ALL")

    assert api_payload["total_count"] == len(engine_data)
    assert api_payload["asset_filter"] == "ALL"

    api_items = api_payload["items"]
    assert len(api_items) == len(engine_data)

    for api_item, engine_item in zip(api_items, engine_data):
        assert api_item["symbol"] == engine_item["symbol"]
        assert api_item["display"] == engine_item["display"]
        assert api_item["name"] == engine_item["name"]
        assert api_item["asset_class"] == engine_item["asset_class"]
        assert api_item["bias_4h"] == engine_item["bias_4h"]
        assert api_item["bias_15m"] == engine_item["bias_15m"]
        assert api_item["setup_state"] == engine_item["setup_state"]
        assert api_item["edge_score"] == pytest.approx(engine_item["edge_score"])
        assert api_item["macro_score"] == pytest.approx(engine_item["macro_score"])
        assert api_item["agreement_pct"] == pytest.approx(engine_item["agreement_pct"])
        assert api_item["data_quality"] == engine_item["data_quality"]
        assert api_item["mode"] == engine_item["mode"]


def test_api_watchlist_filtering_parity():
    """Verify asset class filtering in /api/watchlist?asset_class=FOREX."""
    response = client.get("/api/watchlist?asset_class=FOREX")
    assert response.status_code == 200
    api_payload = response.json()

    engine_data = TradingWorkspaceCockpit.get_watchlist_data("FOREX")
    assert api_payload["total_count"] == len(engine_data)

    for item in api_payload["items"]:
        assert item["asset_class"] == "FOREX"


def test_api_watchlist_search_parity():
    """Verify substring search filtering in /api/watchlist?search=GOLD."""
    response = client.get("/api/watchlist?search=GOLD")
    assert response.status_code == 200
    api_payload = response.json()

    engine_data = TradingWorkspaceCockpit.get_watchlist_data(search_query="GOLD")
    assert api_payload["total_count"] == len(engine_data)
    assert api_payload["items"][0]["symbol"] == "XAUUSD"


# -----------------------------------------------------------------------------
# 3. Market Snapshot Endpoint & Semantic Parity Tests
# -----------------------------------------------------------------------------
def test_api_market_snapshot_xauusd_parity():
    """Verify /api/market/snapshot/XAUUSD returns correct MTF bias and metadata."""
    response = client.get("/api/market/snapshot/XAUUSD")
    assert response.status_code == 200
    snapshot = response.json()

    engine_mtf = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("XAUUSD")

    assert snapshot["symbol"] == "XAUUSD"
    assert snapshot["display"] == "XAUUSD"
    assert snapshot["mtf_bias"] == engine_mtf
    assert snapshot["setup_state"] == "SETUP READY"
    assert snapshot["edge_score"] == pytest.approx(65.0)
    assert snapshot["live_broker_transmission"] == "BLOCKED"
    assert snapshot["cached"] is True
    assert "session" in snapshot


def test_api_market_snapshot_usdjpy_parity():
    """Verify /api/market/snapshot/USDJPY returns correct MTF bias and metadata."""
    response = client.get("/api/market/snapshot/USDJPY")
    assert response.status_code == 200
    snapshot = response.json()

    engine_mtf = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("USDJPY")

    assert snapshot["symbol"] == "USDJPY"
    assert snapshot["display"] == "USDJPY"
    assert snapshot["mtf_bias"] == engine_mtf
    assert snapshot["setup_state"] == "WATCHING"
    assert snapshot["edge_score"] == pytest.approx(40.0)


# -----------------------------------------------------------------------------
# 4. Read-Only Constraint Verification
# -----------------------------------------------------------------------------
def test_api_stage2_read_only_strictly_enforced():
    """Verify that Stage 2 does not allow write mutations."""
    post_res = client.post("/api/watchlist", json={"symbol": "MUTATION_TEST"})
    assert post_res.status_code == 405  # Method Not Allowed

    put_res = client.put("/api/market/snapshot/XAUUSD", json={"price": 9999.0})
    assert put_res.status_code == 405  # Method Not Allowed

    delete_res = client.delete("/api/health")
    assert delete_res.status_code == 405  # Method Not Allowed
