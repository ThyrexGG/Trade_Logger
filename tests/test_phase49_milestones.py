"""
Phase 49 — Tests for 14-Stage Sample Milestones
"""

import pytest
from xauusd_forward_statistical_monitoring import (
    SequentialEvidenceGovernanceEngine,
    FORWARD_MILESTONES,
)


def test_milestone_structure():
    """Validates 14 deterministic research milestones."""
    assert len(FORWARD_MILESTONES) == 14
    assert FORWARD_MILESTONES == [0, 1, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500]


def test_milestone_evaluation_at_n0():
    """Validates milestone progression evaluation at N=0."""
    res = SequentialEvidenceGovernanceEngine.evaluate_milestones(actual_n=0)
    assert res["current_n"] == 0
    assert res["next_milestone"] == 1
    assert res["trades_remaining"] == 1
    assert len(res["milestone_roadmap"]) == 14
    assert res["milestone_roadmap"][0]["is_reached"] is True  # Milestone 0 is reached
    assert res["milestone_roadmap"][1]["is_reached"] is False  # Milestone 1 is pending


def test_milestone_evaluation_at_n35():
    """Validates milestone progression evaluation at N=35."""
    res = SequentialEvidenceGovernanceEngine.evaluate_milestones(actual_n=35)
    assert res["current_n"] == 35
    assert res["next_milestone"] == 50
    assert res["trades_remaining"] == 15
