"""
Phase 50 — Tests for Strict Dataset Isolation & Unpooled Separation
"""

import pytest
from xauusd_forward_lifecycle import ForwardDatasetIsolationGuard
from xauusd_forward_statistical_monitoring import CanonicalForwardDatasetEngine


def test_dataset_isolation_guard():
    """Validates that historical baseline IDs and forward observations remain strictly disjoint."""
    guard = ForwardDatasetIsolationGuard.verify_isolation()
    assert guard["is_isolated"] is True
    assert guard["overlap_count"] == 0
    assert guard["historical_baseline_n"] == 82
    assert guard["historical_expectancy_r"] == 0.637
