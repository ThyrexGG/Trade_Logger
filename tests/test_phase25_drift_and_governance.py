"""
Unit tests for Phase 25 — Drift Monitoring, Governance, Next Action Advisor, and Integrity Panel.
"""

import pytest
from xauusd_research_governance import WatchNextAdvisor, ResearchIntegrityAuditor, ForwardDecisionCenter
from xauusd_forward_integrity import StrategyContractIntegrityGuard


def test_watch_next_advisor_guidance_scenarios():
    # Verify advisor returns actionable structure
    advice = WatchNextAdvisor.get_next_action_advice(mode="PAPER")
    assert "main_advice" in advice
    assert "reasons" in advice
    assert "action" in advice
    assert len(advice["reasons"]) > 0
    assert len(advice["checkpoints"]) >= 5


def test_research_integrity_auditor_evaluation():
    integ = ResearchIntegrityAuditor.evaluate_integrity()
    assert integ["overall_status"] == "PASS"
    assert integ["all_passed"] is True
    assert len(integ["items"]) == 8
    valid_statuses = {"PASS", "FROZEN", "LOCKED", "ISOLATED", "100% MATCH", "0 DETECTED", "HEALTHY", "ACTIVE", "DISABLED"}
    for item in integ["items"]:
        assert item["status"] in valid_statuses


def test_frozen_strategy_immutability():
    # Assert contract hash check works
    immut = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert immut["integrity_status"] == "FROZEN & LOCKED"
    assert immut["live_automation_blocked"] is True


def test_decision_center_summary_generation():
    dec = ForwardDecisionCenter.get_decision_center_summary(mode="PAPER")
    assert dec["strategy"] == "XAUUSD TRUE MTF ICT/SMC"
    assert "PHASE 21 — FROZEN & IMMUTABLE" in dec["contract_status"]
    assert "DISABLED PERMANENTLY" in dec["live_automation"]
    assert len(dec["synthesis_text"]) > 20
