# -*- coding: utf-8 -*-
"""
Phase 60 - Test Unified Trading Workspace Cockpit UX, Watchlist Filtering & Risk Previews
"""
import pytest
import pandas as pd
from trading_workspace_cockpit import TradingWorkspaceCockpit, WATCHLIST_SYMBOLS


def test_watchlist_data_filtering():
    """Verify that watchlist data can be filtered by asset class or retrieved as complete list."""
    all_data = TradingWorkspaceCockpit.get_watchlist_data("ALL")
    assert len(all_data) == len(WATCHLIST_SYMBOLS)
    assert len(all_data) >= 8

    fx_data = TradingWorkspaceCockpit.get_watchlist_data("FOREX")
    assert len(fx_data) >= 3
    for item in fx_data:
        assert item["asset_class"] == "FOREX"

    cmd_data = TradingWorkspaceCockpit.get_watchlist_data("COMMODITY")
    assert len(cmd_data) >= 2
    for item in cmd_data:
        assert item["asset_class"] == "COMMODITY"

    idx_data = TradingWorkspaceCockpit.get_watchlist_data("INDEX")
    assert len(idx_data) >= 2
    for item in idx_data:
        assert item["asset_class"] == "INDEX"


def test_mtf_bias_hierarchy_output():
    """Verify that MTF bias hierarchy produces 6 timeframe layers for XAUUSD and other assets."""
    xau_mtf = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("XAUUSD")
    assert "1D" in xau_mtf
    assert "4H" in xau_mtf
    assert "1H" in xau_mtf
    assert "15M" in xau_mtf
    assert "5M" in xau_mtf
    assert "1M" in xau_mtf
    assert xau_mtf["1M"] in ["ENTRY READY", "WAITING", "STANDBY"]

    uj_mtf = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("USDJPY")
    assert len(uj_mtf) == 6
    assert "1D" in uj_mtf


def test_active_positions_strip_empty_state(monkeypatch):
    """Verify that empty DataFrame renders intentional empty state without crashing."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)
        
    import streamlit as st
    monkeypatch.setattr(st, "markdown", fake_markdown)

    empty_df = pd.DataFrame()
    TradingWorkspaceCockpit.render_active_positions_strip(empty_df)
    
    assert len(called) >= 1
    combined_html = "".join(called)
    assert "NO ACTIVE POSITIONS" in combined_html
    assert "tl-empty-state" in combined_html
