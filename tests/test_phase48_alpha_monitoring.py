"""
Phase 48 — Tests for Observational Alpha Decay Monitoring (Zero Optimization Invariant)
"""

import pytest
from xauusd_forward_lifecycle import ForwardAlphaDecayObservationalMonitor


def test_alpha_decay_monitor_empty_dataset():
    metrics = ForwardAlphaDecayObservationalMonitor.calculate_observational_metrics(mode="PAPER")
    assert metrics["historical_expectancy_r"] == 0.637
    if metrics["forward_n"] == 0:
        assert "INSUFFICIENT SAMPLE SIZE" in metrics["sample_status"]
        assert "NO FORWARD EVIDENCE AVAILABLE" in metrics["decay_verdict"]
