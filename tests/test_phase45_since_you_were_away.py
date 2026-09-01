"""
Phase 45 — Since You Were Away Forensic Audit Test Suite
Validates startup forensic report synthesis and plain-language operational verdict.
"""

import pytest
from xauusd_continuous_forward_ops import SinceYouWereAwayAuditor


def test_since_you_were_away_audit():
    """Validates Since You Were Away forensic report synthesis."""
    audit = SinceYouWereAwayAuditor.audit_since_you_were_away("XAUUSD")

    assert "verdict" in audit
    assert "verdict_color" in audit
    assert "summary_text" in audit
    assert "forward_paper_n" in audit
    assert audit["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert audit["live_automation"] == "DISABLED_PERMANENTLY"
