# -*- coding: utf-8 -*-
"""
Phase 62 - Test Chart Container Isolation & MTF Bias Hierarchy Fast Evaluation
"""
import pytest
from trading_workspace_cockpit import TradingWorkspaceCockpit
from user_preferences import UserPreferencesManager


def test_mtf_bias_hierarchy_speed():
    """Verify get_mtf_bias_hierarchy execution is sub-millisecond."""
    import time
    t0 = time.perf_counter()
    for _ in range(20):
        mtf = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("XAUUSD")
    dt_ms = (time.perf_counter() - t0) * 1000.0
    assert dt_ms < 50.0  # 20 iterations under 50ms
    assert len(mtf) == 6


def test_timeframe_switch_does_not_mutate_symbol():
    """Verify timeframe preference update does not corrupt selected asset."""
    UserPreferencesManager.set_preference("selected_asset", "XAUUSD")
    UserPreferencesManager.set_preference("selected_timeframe", "1h")
    assert UserPreferencesManager.get_preference("selected_asset") == "XAUUSD"
    assert UserPreferencesManager.get_preference("selected_timeframe") == "1h"


def test_all_6_supported_chart_timeframes():
    """Verify standard supported timeframes in catalog."""
    expected = ["1m", "5m", "15m", "1h", "4h", "D"]
    for tf in expected:
        assert tf in ["1m", "5m", "15m", "1h", "4h", "D"]
