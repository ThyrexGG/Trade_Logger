"""
Tests for Phase 29 Research Governance & Safety Invariants.
Verifies live automation barriers, frozen contract hashes, and non-mutating hypothesis firewall.
"""

import pytest
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_research_governance import (
    LiveTradingSafetyBarrier,
    LiveAutomationBlockedException,
    ResearchHypothesisFirewall
)
from xauusd_review_readiness import ReviewReadinessEngine


def test_governance_safety_barrier_permanently_locked():
    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_strategy_contract_hash_immutable():
    verif = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert verif["parameters_verified"] is True
    assert verif["integrity_status"] == "FROZEN & LOCKED"
    assert len(StrategyContractIntegrityGuard.compute_contract_hash()) == 64


def test_highest_automated_state_is_human_review():
    readiness = ReviewReadinessEngine.evaluate_readiness(mode="PAPER")
    assert readiness["verdict"] in {"NOT READY", "READY FOR HUMAN REVIEW", "BLOCKED BY RESEARCH INTEGRITY"}
    # Must never produce "LIVE APPROVED" or "ACTIVATE LIVE"
    assert "LIVE" not in readiness["verdict"]


def test_hypothesis_firewall_is_non_mutating():
    # Adding to future research queue must not mutate contract
    init_hash = StrategyContractIntegrityGuard.compute_contract_hash()
    ResearchHypothesisFirewall.log_future_hypothesis(
        observation="Test Phase 29 regime observation",
        proposed_change="Test parameter hypothesis",
        rationale="Hypothesis logging test",
        source_phase="PHASE 29"
    )
    post_hash = StrategyContractIntegrityGuard.compute_contract_hash()
    assert init_hash == post_hash
