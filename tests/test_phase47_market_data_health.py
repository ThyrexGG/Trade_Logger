"""
Phase 47 — Market Data & Morning Summary Test Suite
Validates morning summary synthesis.
"""

import pytest
from xauusd_forward_evidence_collection import HumanReadableMorningSummary


def test_morning_summary_synthesis():
    """Validates plain-language morning summary output."""
    summary = HumanReadableMorningSummary.generate_morning_summary("XAUUSD")
    assert "summary_text" in summary
    assert "verdict" in summary
    assert "verdict_color" in summary
    assert summary["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert summary["live_automation"] == "DISABLED_PERMANENTLY"
