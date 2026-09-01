"""
Phase 50 — Tests for 8-Link Forensic Evidence Chain Traceability
"""

import pytest
from xauusd_forward_end_to_end_proof import ForensicTraceabilityVerifier


def test_forensic_trace_non_existent_signal():
    """Validates trace on missing signal gracefully reports SIGNAL_NOT_FOUND."""
    res = ForensicTraceabilityVerifier.verify_observation_chain("NON_EXISTENT_SIG_12345")
    assert res["chain_intact"] is False
    assert res["verdict"] == "SIGNAL_NOT_FOUND"
    assert res["traceability_score"] == 0.0
