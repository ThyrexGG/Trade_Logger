"""
Phase 47 — Eligibility Gate Test Suite
Validates 11-state eligibility gate across valid, future timestamp, and contract mismatch scenarios.
"""

from datetime import datetime, timezone, timedelta
import pytest
from xauusd_forward_evidence_collection import ForwardEvidenceEligibilityGate


def test_eligibility_gate_valid_record():
    """Validates eligible observation record."""
    obs = {
        "observation_id": "OBS_ELIGIBLE_1",
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "entry_price": 2500.0,
        "r_multiple": 1.5,
        "strategy_contract_hash": "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    }
    res = ForwardEvidenceEligibilityGate.evaluate_eligibility(obs)
    assert res["is_eligible"] is True
    assert res["eligibility_state"] == "ELIGIBLE"


def test_eligibility_gate_future_timestamp():
    """Validates lookahead rejection on future timestamp."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    obs = {
        "observation_id": "OBS_FUTURE_1",
        "entry_time": future_time,
        "entry_price": 2500.0,
        "r_multiple": 1.5,
        "strategy_contract_hash": "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    }
    res = ForwardEvidenceEligibilityGate.evaluate_eligibility(obs)
    assert res["is_eligible"] is False
    assert res["eligibility_state"] == "LOOKAHEAD_VIOLATION"


def test_eligibility_gate_contract_mismatch():
    """Validates rejection on strategy contract mutation."""
    obs = {
        "observation_id": "OBS_MUTATED_1",
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "entry_price": 2500.0,
        "r_multiple": 1.5,
        "strategy_contract_hash": "MUTATED_HASH_123"
    }
    res = ForwardEvidenceEligibilityGate.evaluate_eligibility(obs)
    assert res["is_eligible"] is False
    assert res["eligibility_state"] == "CONTRACT_MISMATCH"
