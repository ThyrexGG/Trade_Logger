# -*- coding: utf-8 -*-
"""
Phase 61 - Test Watchlist Data Fields, Filtering, Search & Setup States
"""
import pytest
from trading_workspace_cockpit import TradingWorkspaceCockpit, WATCHLIST_SYMBOLS


def test_watchlist_10_quantitative_fields():
    """Verify that watchlist records provide all 10 quantitative fields."""
    data = TradingWorkspaceCockpit.get_watchlist_data("ALL")
    assert len(data) >= 8

    required_fields = [
        "symbol", "display", "name", "asset_class", "price",
        "spread", "bias_4h", "bias_15m", "setup_state",
        "edge_score", "macro_score", "agreement_pct", "data_quality"
    ]

    for item in data:
        for f in required_fields:
            assert f in item, f"Missing field {f} in watchlist item {item['symbol']}"


def test_watchlist_search_filtering():
    """Verify quick search filter on symbol and name."""
    gold_res = TradingWorkspaceCockpit.get_watchlist_data("ALL", search_query="gold")
    assert len(gold_res) >= 1
    assert gold_res[0]["symbol"] == "XAUUSD"

    oil_res = TradingWorkspaceCockpit.get_watchlist_data("ALL", search_query="oil")
    assert len(oil_res) >= 1
    assert oil_res[0]["symbol"] == "USOIL"
