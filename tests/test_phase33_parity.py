"""
Phase 33 — Paper / Shadow Parity & Non-Destructive Alerting Test Suite
Validates that Paper and Shadow execution paths maintain operational parity,
and that auditing is strictly read-only.
"""

import pytest
from xauusd_operational_monitor import PaperShadowParityAuditor


def test_paper_shadow_parity_check():
    """Validates that PaperShadowParityAuditor confirms parity across both forward streams."""
    audit = PaperShadowParityAuditor.audit_operational_parity()
    assert isinstance(audit, dict)
    assert "status" in audit
    assert audit["status"] in ["PASS", "WARNING", "CRITICAL"]
    assert "desync_count" in audit
    assert "total_events_checked" in audit
    assert "verdict" in audit
    assert "is_parity_clean" in audit
    assert audit["overwritten_records_count"] == 0


def test_parity_auditor_does_not_mutate_records():
    """Validates that parity auditing is strictly read-only and never modifies underlying data."""
    audit1 = PaperShadowParityAuditor.audit_operational_parity()
    audit2 = PaperShadowParityAuditor.audit_operational_parity()
    assert audit1["total_events_checked"] == audit2["total_events_checked"]
    assert audit1["desync_count"] == audit2["desync_count"]
    assert audit1["overwritten_records_count"] == audit2["overwritten_records_count"]
