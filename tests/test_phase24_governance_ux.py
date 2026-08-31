"""
Unit tests for Phase 24 Research Governance, Watch Next Advisor & Integrity Panel.
"""

import pytest
import re
from xauusd_research_governance import WatchNextAdvisor, ResearchIntegrityAuditor, ForwardDecisionCenter, LiveTradingSafetyBarrier
from research_explanations import METRIC_CATALOG


def test_watch_next_advisor_checkpoints():
    """Verify that WatchNextAdvisor generates structured, rule-driven checkpoints."""
    checkpoints = WatchNextAdvisor.get_watch_next_checkpoints(mode="PAPER")
    assert len(checkpoints) >= 4
    
    for chk in checkpoints:
        assert "category" in chk
        assert "priority" in chk
        assert chk["priority"] in ["HIGH", "MEDIUM", "NORMAL", "LOW"]
        assert "checkpoint" in chk
        assert "governance_rule" in chk
        assert "action" in chk


def test_research_integrity_auditor_panel():
    """Verify the 8-point research integrity panel data."""
    panel_items = ResearchIntegrityAuditor.get_integrity_panel_data()
    assert len(panel_items) == 8
    
    item_names = [it["item"] for it in panel_items]
    assert "Strategy Contract" in item_names
    assert "Historical Holdout" in item_names
    assert "Forward Dataset" in item_names
    assert "Paper/Shadow Parity" in item_names
    assert "Lookahead Protection" in item_names
    assert "Data Feed Quality" in item_names
    assert "Hypothesis Firewall" in item_names
    assert "Live Automation" in item_names

    # Check live automation is disabled
    live_item = next(it for it in panel_items if it["item"] == "Live Automation")
    assert live_item["status"] == "DISABLED"


def test_forward_decision_center_summary_fields():
    """Verify ForwardDecisionCenter synthesis, progress text, and sample reliability."""
    summary = ForwardDecisionCenter.get_decision_center_summary(mode="PAPER")
    
    assert "strategy" in summary
    assert "contract_status" in summary
    assert "trades_N" in summary
    assert "progress_pct" in summary
    assert "progress_text" in summary
    assert "sample_reliability_explanation" in summary
    assert "synthesis_text" in summary
    assert "next_milestone" in summary
    assert "live_automation" in summary
    assert "DISABLED" in summary["live_automation"]


def test_prohibited_certainty_words():
    """Verify that fake-certainty words are strictly absent from METRIC_CATALOG and synthesis templates."""
    prohibited_words = [
        r"\bguaranteed\b",
        r"\bproven profitable\b",
        r"\bwill make money\b",
        r"\bsafe\b",
        r"\bcertain\b",
        r"\bconfirmed edge\b"
    ]
    
    # Check metric catalog texts
    for metric_id, data in METRIC_CATALOG.items():
        text_corpus = " ".join([str(v) for v in data.values()]).lower()
        for p_word in prohibited_words:
            assert not re.search(p_word, text_corpus), f"Prohibited word '{p_word}' found in METRIC_CATALOG[{metric_id}]"

    # Check Decision Center summary
    dec = ForwardDecisionCenter.get_decision_center_summary()
    dec_corpus = " ".join([str(v) for v in dec.values()]).lower()
    for p_word in prohibited_words:
        assert not re.search(p_word, dec_corpus), f"Prohibited word '{p_word}' found in ForwardDecisionCenter summary"
