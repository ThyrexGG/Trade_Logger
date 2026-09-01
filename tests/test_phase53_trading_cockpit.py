"""
Phase 53 — Tests for Unified Trading Workspace Cockpit
"""

import pytest
import pandas as pd
from trading_workspace_cockpit import TradingWorkspaceCockpit, WATCHLIST_SYMBOLS


def test_watchlist_data_structure():
    w_data = TradingWorkspaceCockpit.get_watchlist_data()
    assert isinstance(w_data, list)
    assert len(w_data) == len(WATCHLIST_SYMBOLS)
    
    for item in w_data:
        assert "symbol" in item
        assert "display" in item
        assert "price" in item
        assert "bias_4h" in item
        assert "bias_15m" in item
        assert "setup_state" in item
        assert "mode" in item
        assert item["mode"] == "PAPER"


def test_mtf_bias_hierarchy():
    xau_mtf = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("XAUUSD")
    assert isinstance(xau_mtf, dict)
    assert "1D" in xau_mtf
    assert "4H" in xau_mtf
    assert "15M" in xau_mtf
    assert "1M" in xau_mtf
    assert xau_mtf["1D"] in ["BULLISH", "BEARISH", "NEUTRAL"]

    jpy_mtf = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("USDJPY")
    assert jpy_mtf["1D"] == "BULLISH"
