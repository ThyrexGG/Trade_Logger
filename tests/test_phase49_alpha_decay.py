"""
Phase 49 — Tests for Non-Invasive Alpha Decay Monitoring
"""

import pytest
from xauusd_forward_statistical_monitoring import AlphaDecayStatisticalMonitor


def test_alpha_decay_empty_state():
    """Validates alpha decay monitor output at N=0."""
    res = AlphaDecayStatisticalMonitor.audit_alpha_stability({"trades_n": 0})
    assert res["decay_state"] == "INSUFFICIENT FORWARD EVIDENCE (N = 0)"
    assert res["expectancy_deterioration"] is False
    assert res["loss_clustering_detected"] is False


def test_alpha_decay_detection():
    """Validates alpha decay alert on negative expectancy and loss clustering."""
    res = AlphaDecayStatisticalMonitor.audit_alpha_stability({
        "trades_n": 20,
        "expectancy_r": -0.40,
        "loss_streak": 5,
        "max_drawdown_r": 6.5
    })
    assert "POTENTIAL ALPHA DECAY" in res["decay_state"]
    assert res["expectancy_deterioration"] is True
    assert res["loss_clustering_detected"] is True
    assert res["action_required"] == "RESEARCH REVIEW REQUIRED"
