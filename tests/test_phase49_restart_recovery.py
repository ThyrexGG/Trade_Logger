"""
Phase 49 — Tests for Restart Recovery & Determinism
"""

import pytest
from xauusd_forward_statistical_monitoring import RestartDeterminismAuditor


def test_restart_recovery_determinism():
    """Validates that consecutive evaluations produce identical fingerprints and metrics without state drift."""
    res = RestartDeterminismAuditor.verify_restart_determinism(mode="PAPER")
    assert res["is_deterministic"] is True
    assert res["status"] == "PASS (DETERMINISTIC)"
    assert res["evaluation_1_fingerprint"] == res["evaluation_2_fingerprint"]
    assert res["evaluation_1_n"] == res["evaluation_2_n"]
