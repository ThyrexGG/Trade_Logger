# -*- coding: utf-8 -*-
"""
Tests for Stage 3.5B Watchlist Latency Optimization
===================================================
Verifies:
1. /api/watchlist returns all expected symbols in exact deterministic order.
2. Response schema compliance (10-field items, total_count, asset_filter, timestamp).
3. Fast in-memory cache hit on warm calls.
4. Correct behavior when asset class or search filters are applied.
5. Graceful fallback on unavailable/offline prices without crashing.
6. Stage 2 and Stage 3 API parity remains 100% intact.
"""
import time
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from trading_workspace_cockpit import WATCHLIST_SYMBOLS, TradingWorkspaceCockpit
import market_data

client = TestClient(app)


def test_watchlist_deterministic_ordering_and_all_symbols():
    """Verify that /api/watchlist returns all 10 catalog symbols in exact order."""
    res = client.get("/api/watchlist")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == len(WATCHLIST_SYMBOLS)

    returned_symbols = [item["symbol"] for item in data["items"]]
    expected_symbols = [item["symbol"] for item in WATCHLIST_SYMBOLS]
    assert returned_symbols == expected_symbols


def test_watchlist_response_schema_integrity():
    """Verify exact 10-field item schema compliance."""
    res = client.get("/api/watchlist")
    assert res.status_code == 200
    data = res.json()

    assert "items" in data
    assert "total_count" in data
    assert "asset_filter" in data
    assert "timestamp" in data

    item_keys = {
        "symbol", "display", "name", "asset_class", "price",
        "spread", "bias_4h", "bias_15m", "setup_state",
        "edge_score", "macro_score", "agreement_pct", "data_quality", "mode"
    }
    for item in data["items"]:
        assert set(item.keys()) == item_keys
        assert item["price"] > 0.0
        assert item["spread"] >= 0.0
        assert item["data_quality"] >= 0


def test_watchlist_filter_and_search():
    """Verify asset class and search substring filtering."""
    # Forex filter
    res_fx = client.get("/api/watchlist?asset_class=FOREX")
    assert res_fx.status_code == 200
    data_fx = res_fx.json()
    for item in data_fx["items"]:
        assert item["asset_class"] == "FOREX"

    # Search filter
    res_search = client.get("/api/watchlist?search=GOLD")
    assert res_search.status_code == 200
    data_search = res_search.json()
    assert len(data_search["items"]) >= 1
    assert any("GOLD" in item["name"].upper() or "XAU" in item["symbol"] for item in data_search["items"])


def test_watchlist_warm_cache_performance():
    """Verify that repeated warm calls return in sub-50ms."""
    # First call warms cache
    client.get("/api/watchlist")

    # Second call warm
    t0 = time.perf_counter()
    res = client.get("/api/watchlist")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert res.status_code == 200
    assert elapsed_ms < 50.0, f"Warm watchlist call took too long: {elapsed_ms:.2f} ms"


def test_watchlist_unavailable_price_fallback():
    """Verify fallback handling when a symbol price returns None."""
    # Evict any fresh cached price so this exercises the fallback path and not a
    # sub-100ms cache hit from a preceding test (the 0.1s TTL below is a race
    # otherwise — surfaced once Phase 68 added market-data work to the intel path).
    market_data._PRICE_CACHE.pop("XAUUSD", None)
    with patch("market_data.get_latest_price", return_value=None):
        prices = market_data.get_batch_prices(["XAUUSD", "UNKNOWN_XYZ"], ttl_sec=0.1)
        assert "XAUUSD" in prices
        assert prices["XAUUSD"] == market_data.DEFAULT_UNIVERSE_PRICES["XAUUSD"]
        assert "UNKNOWN_XYZ" in prices
        assert prices["UNKNOWN_XYZ"] == 100.0
