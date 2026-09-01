"""
Phase 46 — Sample Milestones V2 Test Suite
Validates milestone calculation and progress toward next milestone across 14 milestones.
"""

import pytest
from xauusd_forward_decision_gate import SampleMilestoneEngineV2


def test_milestone_evaluation_n0():
    """Validates milestone evaluation at N = 0."""
    m0 = SampleMilestoneEngineV2.evaluate_milestones(0)
    assert m0["current_n"] == 0
    assert m0["current_milestone"] == 0
    assert m0["next_milestone"] == 1
    assert m0["trades_remaining"] == 1


def test_milestone_evaluation_n15():
    """Validates milestone evaluation at N = 15."""
    m15 = SampleMilestoneEngineV2.evaluate_milestones(15)
    assert m15["current_n"] == 15
    assert m15["current_milestone"] == 10
    assert m15["next_milestone"] == 20
    assert m15["trades_remaining"] == 5
    assert m15["completion_pct_toward_next"] == 50.0
