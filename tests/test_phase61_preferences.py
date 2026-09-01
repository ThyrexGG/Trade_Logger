# -*- coding: utf-8 -*-
"""
Phase 61 - Test User Preferences Storage, Session Caching & SQLite Persistence
"""
import pytest
import streamlit as st
from user_preferences import UserPreferencesManager, DEFAULT_PREFERENCES


def test_user_preferences_initialization():
    """Verify that preferences engine initializes session state with default keys."""
    prefs = UserPreferencesManager.initialize_preferences()
    assert isinstance(prefs, dict)
    for k in DEFAULT_PREFERENCES:
        assert k in prefs


def test_user_preferences_get_set():
    """Verify getter and setter functions with in-memory and SQLite roundtrip."""
    UserPreferencesManager.set_preference("selected_asset", "USDJPY", persist_to_db=True)
    val = UserPreferencesManager.get_preference("selected_asset")
    assert val == "USDJPY"

    UserPreferencesManager.set_preference("watchlist_filter", "FOREX", persist_to_db=True)
    val_filter = UserPreferencesManager.get_preference("watchlist_filter")
    assert val_filter == "FOREX"


def test_user_preferences_reset():
    """Verify reset to defaults."""
    UserPreferencesManager.reset_to_defaults()
    assert UserPreferencesManager.get_preference("selected_asset") == "XAUUSD"
    assert UserPreferencesManager.get_preference("active_workspace_layout") == "DEFAULT"
