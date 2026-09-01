"""
TradeLogger Phase 59 — UI Responsiveness & Diagnostics Telemetry Tests
======================================================================
Validates performance diagnostics metric recording, timer context manager,
and UI state structures.
"""

import time
import pytest
from performance_diagnostics import PerformanceDiagnostics, ProfileTimer


def test_performance_diagnostics_timer():
    """Verify ProfileTimer context manager records duration."""
    PerformanceDiagnostics.reset()
    
    with ProfileTimer("test_component"):
        time.sleep(0.01)  # 10ms
        
    metrics = PerformanceDiagnostics.get_metrics_summary()
    assert "test_component" in metrics["components"]
    comp = metrics["components"]["test_component"]
    assert comp["count"] == 1
    assert comp["avg_ms"] >= 8.0  # ~10ms


def test_cache_telemetry_tracking():
    """Verify cache hit and miss tracking."""
    PerformanceDiagnostics.reset()
    
    PerformanceDiagnostics.record_cache_hit("market_scanner")
    PerformanceDiagnostics.record_cache_hit("market_scanner")
    PerformanceDiagnostics.record_cache_miss("market_scanner")
    
    summary = PerformanceDiagnostics.get_metrics_summary()
    stats = summary["cache_stats"]["market_scanner"]
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["hit_ratio_pct"] == 66.7
