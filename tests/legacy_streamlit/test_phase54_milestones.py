"""
Phase 54 — Tests for 14-Stage Milestone Progression
"""

import pytest
from forward_evidence_cockpit import ForwardEvidenceCockpit
from xauusd_forward_statistical_monitoring import FORWARD_MILESTONES


def test_14_milestones_definition():
    assert len(FORWARD_MILESTONES) == 14
    assert FORWARD_MILESTONES == [0, 1, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500]


def test_milestone_evaluation_structure():
    state = ForwardEvidenceCockpit.load_cockpit_state()
    miles = state["p49"].get("milestones", {})
    assert "current_n" in miles
    assert "next_milestone" in miles
    assert "milestone_roadmap" in miles
    assert len(miles["milestone_roadmap"]) == 14
