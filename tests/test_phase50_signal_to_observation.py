"""
Phase 50 — Tests for Signal Detection to Observation Capture Validation
"""

import pytest
from datetime import datetime, timezone
from xauusd_forward_lifecycle import ForwardSignalPipelineValidator
from xauusd_forward_evidence_collection import ForwardEvidenceEligibilityGate
from xauusd_market_conditions import FROZEN_CONTRACT_HASH


def test_signal_provenance_validation():
    """Validates that signals require required provenance fields without future lookahead."""
    mock_valid_signal = {
        "signal_id": "TEST_SIG_001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "direction": "BUY",
        "bias_1d": "BULLISH",
        "target_4h": "PDH",
        "sweep_15m": "Asian Low Swept",
        "mss_15m": "Bullish MSS",
        "conf_5m": "Confirmed",
        "entry_type_1m": "1M FVG Limit",
        "requested_entry": 2500.0,
        "stop_loss": 2495.0,
        "take_profit": 2515.0,
        "planned_rr": 3.0,
        "session": "London Open",
        "contract_hash": FROZEN_CONTRACT_HASH,
        "execution_mode": "PAPER"
    }

    val = ForwardSignalPipelineValidator.validate_signal_provenance(mock_valid_signal)
    assert isinstance(val, dict)
    assert val.get("valid") is True
    assert val.get("status") == "SIGNAL_PROVENANCE_VALIDATED"


def test_eligibility_gate_rejects_missing_provenance():
    """Validates that eligibility gate rejects signals missing required context."""
    incomplete_signal = {
        "signal_id": "TEST_BAD_001",
        "symbol": "XAUUSD"
    }
    elig = ForwardEvidenceEligibilityGate.evaluate_eligibility(incomplete_signal)
    assert elig.get("is_eligible") is False
    assert elig.get("eligibility_state") != "ELIGIBLE"
