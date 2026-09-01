# -*- coding: utf-8 -*-
"""
Phase 61 - Test Sub-Millisecond Cache Memoization & Non-Regression
"""
import pytest
import time
from market_intelligence_scanner import MarketScannerEngine
from cross_asset_regime_engine import CrossAssetRegimeEngine


def test_scanner_submillisecond_warm_performance():
    """Verify that warm scanner evaluation executes under 50ms via in-memory cache."""
    # First call warms cache
    MarketScannerEngine.scan_universe("ALL")
    
    t0 = time.perf_counter()
    res = MarketScannerEngine.scan_universe("ALL")
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    assert len(res) >= 20
    assert elapsed_ms < 50.0  # Warm cache should return in sub-50ms (typically < 1ms)


def test_regime_submillisecond_warm_performance():
    """Verify that warm regime evaluation executes under 50ms via in-memory cache."""
    CrossAssetRegimeEngine.evaluate_regime()

    t0 = time.perf_counter()
    snap = CrossAssetRegimeEngine.evaluate_regime()
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert snap is not None
    assert elapsed_ms < 50.0
