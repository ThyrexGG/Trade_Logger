"""
Phase 47 — Forensic Verifier & News Context Test Suite
Validates 10-pillar forensic check on forward observations.
"""

import pytest
from xauusd_forward_evidence_collection import OneClickForensicVerifier


def test_one_click_forensic_verifier():
    """Validates 10-pillar forensic verification."""
    obs = {
        "signal_id": "OBS_TEST_1",
        "entry_price": 2500.0,
        "strategy_contract_hash": "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76",
        "execution_mode": "PAPER",
        "status": "COMPLETED"
    }
    ver = OneClickForensicVerifier.verify_observation(obs)
    assert ver["verdict"] == "FORWARD OBSERVATION VERIFIED"
    assert ver["all_passed"] is True
    assert len(ver["pillars"]) == 10
