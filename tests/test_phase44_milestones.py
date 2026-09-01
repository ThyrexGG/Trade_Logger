"""
Phase 44 — Sample Milestone Engine Test Suite
Validates tracking across all 12 milestones: [10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 500].
"""

import pytest
from xauusd_forward_accumulation import SampleMilestoneEngine


def test_sample_milestone_evaluation():
    """Validates all 12 sample milestone evaluations."""
    milestones = SampleMilestoneEngine.evaluate_all_milestones("XAUUSD")

    assert len(milestones) == 12
    targets = [m["target_n"] for m in milestones]
    assert targets == [10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 500]

    for m in milestones:
        assert "is_reached" in m
        assert "status_label" in m
        assert "current_progress_pct" in m
        if not m["is_reached"]:
            assert m["status_label"] == "MILESTONE NOT REACHED"
