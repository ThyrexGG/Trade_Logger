"""
Phase 46 — Research Decision Gate Test Suite
Validates deterministic decision states across sample sizes and expectancies.
"""

import pytest
from xauusd_forward_decision_gate import ResearchDecisionGateEngine


def test_decision_gate_empty():
    """Validates decision gate at N = 0."""
    res = ResearchDecisionGateEngine.evaluate_decision_gate(0, 0.0)
    assert "COLLECTING — NO DECISION POSSIBLE" in res["decision_state"]
    assert res["decision_color"] == "#8a99ad"


def test_decision_gate_early_consistent():
    """Validates decision gate at N = 35 with positive expectancy."""
    res = ResearchDecisionGateEngine.evaluate_decision_gate(35, 0.55)
    assert "FORWARD EVIDENCE CONSISTENT WITH HISTORICAL" in res["decision_state"]
    assert res["decision_color"] == "#00ffcc"


def test_decision_gate_negative_review():
    """Validates decision gate with negative forward expectancy at N = 60."""
    res = ResearchDecisionGateEngine.evaluate_decision_gate(60, -0.25)
    assert "FORWARD EVIDENCE REQUIRES HUMAN REVIEW" in res["decision_state"]
    assert res["decision_color"] == "#ef4444"
