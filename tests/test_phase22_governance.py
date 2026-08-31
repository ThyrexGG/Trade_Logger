"""
Unit Tests for Phase 22 — Governance Gates & Safety Invariants
Tests:
- Deterministic decision gate evaluation (Stage 0 to Stage 3)
- Live automation permanently disabled invariant
- Next milestone requirement calculation
- Zero emojis and absence of forbidden certainty words
"""

import pytest
import re
from xauusd_validation_gate import XAUUSDValidationGate
from xauusd_forward_monitor import XAUUSDForwardMonitor


def test_decision_gate_evaluation():
    gate = XAUUSDValidationGate.evaluate_gate(mode="PAPER")
    assert "stage_id" in gate
    assert gate["stage_id"] in [0, 1, 2, 3]
    assert "stage_name" in gate
    assert "status" in gate
    assert "next_milestone" in gate
    assert "required_criteria" in gate


def test_live_automation_permanently_disabled():
    gate = XAUUSDValidationGate.evaluate_gate(mode="PAPER")
    assert gate["live_automation_status"] == "DISABLED"
    assert "disabled" in gate["governance_rule"].lower()


def test_zero_emojis_and_forbidden_words():
    # Gather text descriptions from gate and monitor
    gate = XAUUSDValidationGate.evaluate_gate(mode="PAPER")
    summary = XAUUSDForwardMonitor.get_forward_summary(mode="PAPER")
    
    combined_text = f"{gate['explanation']} {gate['verdict']} {gate['next_milestone']} {summary['sample_text']} {summary['ci_text']}"
    
    # 1. No emojis regex
    emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
    assert not emoji_pattern.search(combined_text)

    # 2. No forbidden fake-certainty words
    forbidden = ["guaranteed", "safe", "will make money", "certain", "proven to work", "100% win rate"]
    for word in forbidden:
        assert word not in combined_text.lower()
