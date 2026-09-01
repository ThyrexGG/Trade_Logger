"""
Phase 43 — Morning-After Research Audit Test Suite
Validates Morning-After audit synthesis, morning hero decision card, and timeline integration.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_overnight_experiment import MorningAfterAuditSynthesizer


def test_morning_after_audit_synthesis():
    """Validates complete morning audit structure."""
    target_dt = date(2026, 9, 1)
    audit = MorningAfterAuditSynthesizer.synthesize_morning_audit(target_dt)

    assert "morning_hero" in audit
    assert "verdict" in audit["morning_hero"]
    assert "operational_health" in audit
    assert "lifecycle_summary" in audit
    assert "market_context" in audit
    assert "zero_explanation" in audit
    assert "timeline" in audit
    assert audit["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert audit["live_automation"] == "DISABLED_PERMANENTLY"
