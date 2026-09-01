"""
Phase 48 — Tests for Strict Historical vs Forward Dataset Isolation
"""

import pytest
from xauusd_forward_lifecycle import ForwardDatasetIsolationGuard


def test_dataset_isolation_invariants():
    guard = ForwardDatasetIsolationGuard.verify_isolation()
    assert guard["is_isolated"] is True
    assert guard["status"] == "STRICTLY ISOLATED"
    assert guard["overlap_count"] == 0
    assert guard["historical_baseline_n"] == 82
    assert guard["historical_expectancy_r"] == 0.637
