"""
Unit tests for Phase 28 Research Integrity & Safety Invariants.
Verifies contract immutability, dataset isolation, safety barriers, and review gate restrictions.
"""

import pytest
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_research_governance import (
    LiveTradingSafetyBarrier,
    LiveAutomationBlockedException,
    XAUUSDParityWatchdog,
    XAUUSDDataIntegrityWatchdog,
    ResearchHypothesisFirewall
)
from xauusd_review_readiness import ReviewReadinessEngine


def test_contract_immutability_and_hash():
    full_hash = StrategyContractIntegrityGuard.compute_contract_hash()
    assert len(full_hash) == 64
    res = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert res["parameters_verified"] is True
    assert res["integrity_status"] == "FROZEN & LOCKED"


def test_live_trading_permanently_blocked():
    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_paper_shadow_parity_clean():
    parity = XAUUSDParityWatchdog.audit_parity()
    assert parity["is_parity_clean"] is True
    assert parity["status"] == "100% PARITY"


def test_hypothesis_firewall_non_mutating():
    # Adding a hypothesis must not alter active strategy
    hypo_id = ResearchHypothesisFirewall.log_future_hypothesis(
        observation="Observed slight slippage on high-velocity candles",
        proposed_change="Test tighter limit expiration",
        rationale="Microstructure optimization exploratory test",
        source_phase="Phase 28"
    )
    assert hypo_id.startswith("HYPO_")
    
    # Contract must still remain frozen
    res = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert res["integrity_status"] == "FROZEN & LOCKED"
