"""
Phase 50 — Tests for Deterministic Outcome Resolution & Invalidation Invariant
"""

import pytest
from xauusd_forward_lifecycle import ForwardOutcomeLifecycleManager


def test_outcome_state_validation():
    """Validates permitted terminal outcomes."""
    permitted = ForwardOutcomeLifecycleManager.TERMINAL_OUTCOMES
    assert "TP_HIT" in permitted
    assert "SL_HIT" in permitted
    assert "EXPIRED" in permitted
    assert "CANCELLED" in permitted
    assert "INVALIDATED" in permitted
    assert "COMPLETED" in permitted


def test_invalid_outcome_rejected():
    """Validates that undefined outcome states are rejected."""
    with pytest.raises(ValueError):
        ForwardOutcomeLifecycleManager.update_trade_outcome("TEST_SIG_999", "UNKNOWN_STATE")
