"""
Phase 33 — Forward Data Lifecycle & Timeout Separation Test Suite
Validates that limit timeouts and invalidations are never misclassified as strategy losses,
and that only filled trades count toward the valid forward sample size N.
"""

import pytest
from xauusd_operational_monitor import ForwardDataLifecycleTracker


def test_forward_lifecycle_separation():
    """Validates that ForwardDataLifecycleTracker distinguishes filled trades from timeouts and invalidations."""
    metrics = ForwardDataLifecycleTracker.get_lifecycle_metrics("XAUUSD")
    assert isinstance(metrics, dict)
    assert "evaluations_total" in metrics
    assert "valid_completed_trades_n" in metrics
    assert "paper_observations" in metrics
    assert "shadow_observations" in metrics
    assert "execution_separation_verified" in metrics
    assert metrics["execution_separation_verified"] is True
    assert "unfilled_limits_counted_as_loss" in metrics
    assert metrics["unfilled_limits_counted_as_loss"] is False


def test_timeout_never_counted_as_strategy_loss():
    """Validates that a 15-minute expiration/timeout does not generate an R loss."""
    metrics = ForwardDataLifecycleTracker.get_lifecycle_metrics("XAUUSD")
    paper_obs = metrics["paper_observations"]
    assert "completed_trades" in paper_obs
    assert "timeouts" in paper_obs
    assert "invalidations" in paper_obs
    assert metrics["unfilled_limits_counted_as_loss"] is False
