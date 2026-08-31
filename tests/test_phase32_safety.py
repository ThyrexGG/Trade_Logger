"""
Phase 32 — Safety Invariants, Contract Immutability & Lookahead Protection Test Suite
Validates that Strategy Contract SHA-256 hash is unchanged, historical holdout is locked,
live automation is disabled permanently, and news metadata introduces zero lookahead.
"""

import os
import hashlib
import pytest
from datetime import datetime, timezone
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_research_governance import LiveTradingSafetyBarrier, LiveAutomationBlockedException
from xauusd_market_conditions import FROZEN_CONTRACT_HASH, MarketConditionProvenance


def test_strategy_contract_hash_exact_match():
    """Validates that PHASE_21_XAUUSD_STRATEGY_CONTRACT.md matches exact frozen SHA-256 hash."""
    contract_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)

    with open(contract_path, "rb") as f:
        computed_hash = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()

    assert computed_hash == FROZEN_CONTRACT_HASH
    
    guard = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert guard["parameters_verified"] is True
    assert guard["integrity_status"] == "FROZEN & LOCKED"


def test_live_automation_permanently_locked():
    """Validates that live broker transmission remains permanently disabled."""
    status = LiveTradingSafetyBarrier.enforce_live_barrier("PAPER")
    assert status["live_automation_blocked"] is True
    assert status["status"] == "SAFETY LOCK ACTIVE"

    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_no_lookahead_in_market_condition_provenance():
    """Validates that market condition provenance preserves exact observation timestamp without future leakage."""
    past_time = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)
    meta = MarketConditionProvenance.generate_observation_metadata(past_time)
    assert meta["observation_timestamp"] == past_time.isoformat()
    assert "market_condition_id" in meta
    assert "market_condition_fingerprint" in meta
