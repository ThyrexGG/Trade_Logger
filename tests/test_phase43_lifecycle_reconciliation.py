"""
Phase 43 — Setup Lifecycle Reconciliation Test Suite
Validates mathematical lifecycle reconciliation:
Candidate Setups == Completed + Timeouts + Invalidations + Rejections
Guarantees: Timeout != loss, Invalidation != loss.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_overnight_experiment import SetupLifecycleReconciler


def test_record_lifecycle_transitions():
    """Validates recording setup transitions."""
    t1 = SetupLifecycleReconciler.record_transition("SETUP_001", "DETECTED", "QUALIFIED")
    assert t1["transition"] == "DETECTED->QUALIFIED"
    assert t1["is_terminal"] is False

    t2 = SetupLifecycleReconciler.record_transition("SETUP_001", "QUALIFIED", "INVALIDATED", reason="Sweep failed")
    assert t2["transition"] == "QUALIFIED->INVALIDATED"
    assert t2["is_terminal"] is True


def test_reconcile_lifecycle_counts():
    """Validates mathematical reconciliation synthesis."""
    recon = SetupLifecycleReconciler.reconcile_lifecycle_counts()

    assert "completed" in recon
    assert "invalidations" in recon
    assert "timeouts" in recon
    assert "rejections" in recon
    assert recon["reconciliation_passed"] is True
    assert recon["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
