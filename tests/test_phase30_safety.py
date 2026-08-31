"""
Phase 30 — Safety Invariants, Dataset Isolation & Contract Immutability Tests
Verifies that strategy contract SHA-256 is unchanged, holdout baseline is locked,
live automation is disabled permanently, and dataset pooling is prohibited.
"""

import hashlib
import os
import pytest
from xauusd_research_governance import LiveTradingSafetyBarrier, LiveAutomationBlockedException
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_forward_validator import XAUUSDForwardComparator, XAUUSDForwardJournal


EXPECTED_CONTRACT_HASH = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_strategy_contract_hash_exact_match():
    """Validates that the Strategy Contract SHA-256 hash matches the frozen invariant."""
    contract_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)

    with open(contract_path, "rb") as f:
        computed_hash = hashlib.sha256(f.read()).hexdigest()

    assert computed_hash == EXPECTED_CONTRACT_HASH, (
        f"CRITICAL GOVERNANCE VIOLATION: Contract hash modified! Expected {EXPECTED_CONTRACT_HASH}, got {computed_hash}"
    )


def test_contract_integrity_guard_verification():
    """Validates the automated StrategyContractIntegrityGuard."""
    guard_status = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert guard_status["parameters_verified"] is True
    assert guard_status["integrity_status"] == "FROZEN & LOCKED"


def test_live_automation_permanently_locked():
    """Validates that live automation is disabled and raises LiveAutomationBlockedException."""
    status = LiveTradingSafetyBarrier.enforce_live_barrier(target_state="PAPER")
    assert status["live_automation_blocked"] is True
    assert status["status"] == "SAFETY LOCK ACTIVE"

    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_dataset_isolation_unpooled():
    """Validates that historical holdout, paper, and shadow datasets are never pooled."""
    comp_table = XAUUSDForwardComparator.get_comparative_table()
    assert len(comp_table) == 3

    hist = comp_table[0]
    paper = comp_table[1]
    shadow = comp_table[2]

    # Historical metrics must remain strictly frozen
    assert hist["trades_N"] == 82
    assert hist["expectancy_r"] == "+0.637 R"
    assert hist["win_rate_pct"] == pytest.approx(58.6, abs=0.1)
    assert hist["profit_factor"] == pytest.approx(2.52, abs=0.1)
    assert "Holdout" in hist["dataset"]
    assert "Paper" in paper["dataset"]
    assert "Shadow" in shadow["dataset"]
