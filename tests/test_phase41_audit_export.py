"""
Phase 41 — Audit Export & Governance Invalidation Matrix Test Suite
Validates Markdown report generation, structured JSON audit bundle, and 9-pillar governance matrix.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_evidence_reproducibility import (
    AuditExportSubsystem,
    GovernanceInvalidationMatrix,
)


def test_markdown_audit_report_generation():
    """Validates markdown audit export contains essential sections."""
    target_dt = date(2026, 9, 1)
    md_report = AuditExportSubsystem.generate_markdown_audit_report(target_dt)

    assert "# XAUUSD FORWARD RESEARCH AUDIT REPORT" in md_report
    assert "Strategy Contract Hash" in md_report
    assert "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76" in md_report
    assert "LIVE AUTOMATION STATUS" in md_report.upper()


def test_audit_bundle_generation():
    """Validates JSON audit bundle structure."""
    target_dt = date(2026, 9, 1)
    bundle = AuditExportSubsystem.generate_audit_bundle(target_dt)

    assert "bundle_metadata" in bundle
    assert "snapshot" in bundle
    assert "governance_matrix" in bundle
    assert bundle["governance_matrix"]["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_governance_invalidation_matrix_nine_pillars():
    """Validates 9 pillars of governance matrix."""
    gov = GovernanceInvalidationMatrix.evaluate_governance()

    assert len(gov["pillars"]) == 9
    assert gov["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert gov["live_automation"] == "DISABLED_PERMANENTLY"
