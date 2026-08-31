"""
Phase 33 — Safety Barrier & Strategy Contract Immutability Test Suite
Validates that Strategy Contract SHA-256 hash is unchanged, historical holdout is locked,
dataset isolation is intact, and live broker transmission remains permanently disabled.
"""

import os
import hashlib
import pytest
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_research_governance import LiveTradingSafetyBarrier, LiveAutomationBlockedException
from xauusd_operational_monitor import HistoricalContaminationAuditor
from xauusd_market_conditions import FROZEN_CONTRACT_HASH


def test_strategy_contract_hash_exact_match():
    """Validates that PHASE_21_XAUUSD_STRATEGY_CONTRACT.md matches exact frozen SHA-256 hash."""
    contract_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)

    with open(contract_path, "rb") as f:
        computed_hash = hashlib.sha256(f.read()).hexdigest()

    assert computed_hash == FROZEN_CONTRACT_HASH
    assert computed_hash == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_live_automation_safety_lock_enforced():
    """Validates that live automation is disabled and raises LiveAutomationBlockedException on breach attempt."""
    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_historical_holdout_isolation_and_no_contamination():
    """Validates that historical holdout and forward observations maintain zero ID overlap."""
    audit = HistoricalContaminationAuditor.audit_historical_contamination()
    assert audit["status"] == "PASS"
    assert audit["historical_holdout_n"] == 82
    assert "NONE DETECTED" in audit["verdict"]
    assert "historical_holdout_fingerprint" in audit
    assert len(audit["historical_holdout_fingerprint"]) == 64
