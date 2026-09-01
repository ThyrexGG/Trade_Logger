"""
Phase 46 — Multi-Tier Confidence Intervals Test Suite
Validates bootstrap calculations (90%, 95%, 99%) and insufficient sample protection.
"""

import pytest
from xauusd_forward_decision_gate import MultiTierConfidenceIntervalEngine


def test_confidence_intervals_insufficient():
    """Validates protection when N < 5."""
    res = MultiTierConfidenceIntervalEngine.calculate_multi_tier_ci([1.0, 0.5])
    assert "INSUFFICIENT DATA" in res["status"]
    assert res["is_positive_95"] is False


def test_confidence_intervals_bootstrap_reproducibility():
    """Validates bootstrap CI computation with seed reproducibility."""
    r_list = [1.0, 1.5, -0.5, 2.0, -1.0, 1.2, 0.8, -0.4, 1.1, 0.9]
    res1 = MultiTierConfidenceIntervalEngine.calculate_multi_tier_ci(r_list, seed=42)
    res2 = MultiTierConfidenceIntervalEngine.calculate_multi_tier_ci(r_list, seed=42)

    assert res1["status"] == "COMPUTED"
    assert res1["ci_95"] == res2["ci_95"]
    assert res1["point_estimate"] == res2["point_estimate"]
