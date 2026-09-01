"""
Phase 48 — Tests for Forward Lifecycle Reconciliation and Orphan Auditing
"""

import pytest
from xauusd_forward_lifecycle import ForwardLifecycleReconciliationAudit


def test_database_integrity_audit():
    audit = ForwardLifecycleReconciliationAudit.audit_database_integrity()
    assert isinstance(audit, dict)
    assert "audit_timestamp" in audit
    assert "total_signals" in audit
    assert "dataset_isolation_clean" in audit
    assert audit["dataset_isolation_clean"] is True
    assert audit["historical_baseline_n"] == 82
    assert audit["live_automation_blocked"] is True
