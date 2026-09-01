"""
Phase 45 — Weekly Research Audit Test Suite
Validates weekly audit generation, "What Changed This Week?" delta report, and Markdown export.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_continuous_forward_ops import WeeklyResearchAuditEngine


def test_weekly_audit_generation():
    """Validates weekly audit structure and persistence."""
    target_dt = date(2026, 9, 1)
    audit = WeeklyResearchAuditEngine.generate_weekly_audit(target_dt, "XAUUSD")

    assert "audit_id" in audit
    assert "week_identifier" in audit
    assert "forward_n" in audit
    assert "expectancy_r" in audit
    assert "alpha_decay_state" in audit
    assert "regime_drift_state" in audit
    assert "what_changed_this_week" in audit
    assert audit["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_markdown_weekly_audit_export():
    """Validates deterministic Markdown export scrubbing credentials."""
    target_dt = date(2026, 9, 1)
    md = WeeklyResearchAuditEngine.generate_markdown_weekly_audit(target_dt)

    assert "# PHASE 45 WEEKLY FORWARD RESEARCH AUDIT" in md
    assert "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76" in md
    assert "password" not in md.lower()
    assert "secret" not in md.lower()
