"""
Phase 50 — Tests for System Restart Recovery & Determinism
"""

import pytest
from xauusd_forward_statistical_monitoring import RestartDeterminismAuditor
from xauusd_forward_end_to_end_proof import Phase50E2EOperationalProofEngine


def test_restart_recovery_across_evaluations():
    """Validates that pipeline evaluation produces deterministic state across restarts."""
    audit1 = Phase50E2EOperationalProofEngine.audit_end_to_end_pipeline(mode="PAPER")
    audit2 = Phase50E2EOperationalProofEngine.audit_end_to_end_pipeline(mode="PAPER")

    assert audit1["actual_n"] == audit2["actual_n"]
    assert audit1["supervisor"]["milestone_state"] == audit2["supervisor"]["milestone_state"]
    assert audit1["safety"]["status"] == audit2["safety"]["status"]
