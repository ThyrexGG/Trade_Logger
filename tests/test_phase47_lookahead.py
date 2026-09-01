"""
Phase 47 — Lookahead Protection Test Suite
Validates that future actual values and timestamps remain prohibited.
"""

from datetime import datetime, timezone, timedelta
import pytest
from xauusd_forward_evidence_collection import ForwardEvidenceEligibilityGate


def test_lookahead_future_timestamp_blocked():
    """Validates future timestamp is strictly rejected."""
    future_time = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    obs = {
        "observation_id": "OBS_LOOKAHEAD_1",
        "entry_time": future_time,
        "entry_price": 2500.0,
        "strategy_contract_hash": "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    }
    gate = ForwardEvidenceEligibilityGate.evaluate_eligibility(obs)
    assert gate["is_eligible"] is False
    assert gate["eligibility_state"] == "LOOKAHEAD_VIOLATION"
