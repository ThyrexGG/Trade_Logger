"""
Phase 50 — Tests for Downstream Handoff to Phase 49 Statistical Monitoring
"""

import pytest
from xauusd_forward_end_to_end_proof import Phase50Facade


def test_phase49_integration_handoff():
    """Validates that Phase 50 correctly hands off forward observations to Phase 49."""
    state = Phase50Facade.get_phase50_full_state(mode="PAPER")
    assert "phase49_state" in state
    p49 = state["phase49_state"]
    assert "metrics" in p49
    assert "uncertainty" in p49
    assert "comparison" in p49
    assert "milestones" in p49
    assert p49["metrics"]["trades_n"] == state["pipeline"]["actual_n"]
