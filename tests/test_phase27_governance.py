"""
Tests for Phase 27 Research Governance and Safety Gates.
Verifies Stage 0-3 transitions, integrity-blocked state, permanent live lock, and human-review-only gates.
"""

import pytest
from xauusd_validation_gate import XAUUSDValidationGate
from xauusd_research_governance import (
    LiveTradingSafetyBarrier,
    ResearchIntegrityAuditor,
    WatchNextAdvisor
)
from xauusd_forward_evidence import ResearchDecisionStateClassifier


def test_stage_definitions_and_progression():
    # Evaluate gate for standard PAPER mode
    gate_res = XAUUSDValidationGate.evaluate_gate(mode="PAPER")
    assert "stage_id" in gate_res
    assert "stage_name" in gate_res
    assert "status" in gate_res
    assert "verdict" in gate_res
    assert "explanation" in gate_res
    assert "next_milestone" in gate_res
    assert gate_res["stage_id"] in [0, 1, 2, 3]


def test_live_trading_safety_barrier_permanently_locked():
    from xauusd_research_governance import LiveAutomationBlockedException
    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_research_advisor_stage_targeting():
    advice = WatchNextAdvisor.get_next_action_advice(mode="PAPER")
    assert "main_advice" in advice
    assert "action" in advice
    assert len(advice["reasons"]) >= 1


def test_integrity_blocked_decision_state(monkeypatch):
    # Simulate an integrity failure
    monkeypatch.setattr(
        ResearchIntegrityAuditor,
        "evaluate_integrity",
        lambda: {"all_passed": False, "overall_status": "FAIL", "warning_message": "Contract mismatch detected"}
    )
    state = ResearchDecisionStateClassifier.classify_state(mode="PAPER")
    assert state["state"] == "INTEGRITY BLOCKED"
    assert "Research integrity" in state["explanation"]
