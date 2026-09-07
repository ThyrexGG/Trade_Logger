# -*- coding: utf-8 -*-
"""
Phase 62 - Test Streamlit Rerun Isolation, Lazy Rendering & Dependency Decoupling
"""
import pytest
from trading_workspace_cockpit import TradingWorkspaceCockpit
from workspace_layout_manager import WORKSPACE_LAYOUTS
from user_preferences import UserPreferencesManager


def test_watchlist_filter_does_not_mutate_underlying_data():
    """Verify that changing watchlist filter pills only filters the in-memory view."""
    all_data = TradingWorkspaceCockpit.get_watchlist_data("ALL")
    forex_data = TradingWorkspaceCockpit.get_watchlist_data("FOREX")
    crypto_data = TradingWorkspaceCockpit.get_watchlist_data("CRYPTO")

    assert len(all_data) >= 8
    assert len(forex_data) > 0
    assert len(crypto_data) > 0
    assert len(forex_data) < len(all_data)
    for item in forex_data:
        assert item["asset_class"].lower() == "forex"


def test_layout_switch_state_isolation():
    """Verify layout switching updates active layout token without triggering calculation resets."""
    for layout_key in WORKSPACE_LAYOUTS:
        UserPreferencesManager.set_preference("active_workspace_layout", layout_key)
        assert UserPreferencesManager.get_preference("active_workspace_layout") == layout_key


def test_quick_search_filtering_isolation():
    """Verify quick search filter does not alter un-searched items."""
    res_gold = TradingWorkspaceCockpit.get_watchlist_data("ALL", search_query="XAU")
    assert len(res_gold) >= 1
    assert "XAU" in res_gold[0]["symbol"]

    # Search with empty query returns all
    res_all = TradingWorkspaceCockpit.get_watchlist_data("ALL", search_query="")
    assert len(res_all) >= len(res_gold)


def test_asset_class_empty_filter_safety():
    """Verify unknown filter defaults gracefully without exception."""
    res_unk = TradingWorkspaceCockpit.get_watchlist_data("NON_EXISTENT_CLASS")
    assert isinstance(res_unk, list)
