# -*- coding: utf-8 -*-
"""
Phase 62 - Test State Isolation & Preferences Multi-Thread Stability
"""
import pytest
import threading
from user_preferences import UserPreferencesManager, DEFAULT_PREFERENCES


def test_user_preferences_concurrent_updates():
    """Verify concurrent user preference setting without data corruption."""
    def worker(val):
        for _ in range(50):
            UserPreferencesManager.set_preference("selected_asset", val)

    t1 = threading.Thread(target=worker, args=("XAUUSD",))
    t2 = threading.Thread(target=worker, args=("USDJPY",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    val = UserPreferencesManager.get_preference("selected_asset")
    assert val in ["XAUUSD", "USDJPY"]


def test_preferences_default_values():
    """Verify default values in preferences dictionary."""
    assert DEFAULT_PREFERENCES["selected_asset"] == "XAUUSD"
    assert DEFAULT_PREFERENCES["selected_timeframe"] == "15m"
    assert DEFAULT_PREFERENCES["active_workspace_layout"] == "DEFAULT"
    assert DEFAULT_PREFERENCES["compact_mode"] is False


def test_compact_mode_preference_toggle():
    """Verify compact mode toggle setting."""
    UserPreferencesManager.set_preference("compact_mode", True)
    assert UserPreferencesManager.get_preference("compact_mode") is True
    UserPreferencesManager.set_preference("compact_mode", False)
    assert UserPreferencesManager.get_preference("compact_mode") is False
