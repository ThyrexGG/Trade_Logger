"""
Phase 53 — Tests for Watchlist Component & Multi-Asset Support
"""

import pytest
from trading_workspace_cockpit import WATCHLIST_SYMBOLS, TradingWorkspaceCockpit


def test_watchlist_supported_symbols():
    syms = [s["symbol"] for s in WATCHLIST_SYMBOLS]
    assert "XAUUSD" in syms
    assert "USDJPY" in syms
    assert "EURUSD" in syms
    assert "GBPUSD" in syms
    assert "SPX500" in syms
    assert "NAS100" in syms
    assert "DXY" in syms


def test_watchlist_scanability_badges():
    w_data = TradingWorkspaceCockpit.get_watchlist_data()
    for row in w_data:
        assert row["bias_4h"] in ["BULL", "BEAR", "NEUT"]
        assert row["bias_15m"] in ["BULL", "BEAR", "NEUT"]
        assert row["setup_state"] in ["SETUP READY", "WATCHING", "FLAT"]
