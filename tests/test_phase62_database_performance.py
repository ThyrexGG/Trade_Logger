# -*- coding: utf-8 -*-
"""
Phase 62 - Test Database Performance, Index Optimization & Read-Through Caching
"""
import pytest
import time
import database
from user_preferences import UserPreferencesManager


def test_sqlite_query_speed_and_indexes():
    """Verify that settings queries execute rapidly under index."""
    t0 = time.perf_counter()
    for _ in range(50):
        val = database.get_setting("SYSTEM_STATE", "PAPER")
        assert val is not None
    dt_ms = (time.perf_counter() - t0) * 1000.0
    # 50 query reads should take less than 150ms in SQLite
    assert dt_ms < 150.0


def test_open_positions_query_fast():
    """Verify open positions retrieval latency."""
    t0 = time.perf_counter()
    df_pos = database.get_open_positions()
    dt_ms = (time.perf_counter() - t0) * 1000.0
    assert dt_ms < 50.0  # Fast indexed read


def test_closed_trades_query_speed():
    """Verify closed trades query speed and DataFrame conversion."""
    t0 = time.perf_counter()
    df_trades = database.get_closed_trades()
    dt_ms = (time.perf_counter() - t0) * 1000.0
    assert dt_ms < 100.0


def test_user_preferences_sqlite_read_write():
    """Verify persistent user preferences SQLite table read and write performance."""
    t0 = time.perf_counter()
    UserPreferencesManager.set_preference("selected_asset", "USDJPY", persist_to_db=True)
    val = UserPreferencesManager.get_preference("selected_asset")
    dt_ms = (time.perf_counter() - t0) * 1000.0
    assert dt_ms < 50.0
    assert val == "USDJPY"
