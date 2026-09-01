"""
Unit Tests for Phase 23 — Research Governance, Hypothesis Firewall & Decision Center
Tests:
- Research hypothesis queueing into FUTURE_RESEARCH_QUEUE without mutating strategy
- Forward Decision Center dynamic synthesis generation
- Live trading safety barrier blocking
- Zero emojis and absence of forbidden fake-certainty words
"""

import pytest
import re
import database
from xauusd_research_governance import (
    ResearchHypothesisFirewall,
    ForwardDecisionCenter,
    LiveTradingSafetyBarrier,
    LiveAutomationBlockedException
)


@pytest.fixture(autouse=True)
def init_test_db():
    database.init_db()


def test_research_hypothesis_firewall_queueing():
    hypo_id = ResearchHypothesisFirewall.log_future_hypothesis(
        observation="Forward missed-entry rate is 28%.",
        proposed_change="Consider entry offset adjustment in future research phase.",
        rationale="Improve limit fill capture without altering frozen Phase 21 parameters."
    )
    assert hypo_id.startswith("HYPO_")

    df_q = ResearchHypothesisFirewall.get_queued_hypotheses()
    assert not df_q.empty
    assert hypo_id in df_q["hypothesis_id"].values


def test_forward_decision_center_synthesis():
    summary = ForwardDecisionCenter.get_decision_center_summary(mode="PAPER")
    assert "strategy" in summary
    assert "contract_status" in summary
    assert "synthesis_text" in summary
    assert "next_milestone" in summary
    assert "live_automation" in summary
    assert len(summary["synthesis_text"]) > 20


def test_live_trading_safety_barrier_enforcement():
    # 1. Target live raises LiveAutomationBlockedException
    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.enforce_live_barrier(target_state="LIVE")

    # 2. Target paper succeeds
    barrier = LiveTradingSafetyBarrier.enforce_live_barrier(target_state="PAPER")
    assert barrier["live_automation_blocked"] is True


def test_zero_emojis_and_clean_language():
    summary = ForwardDecisionCenter.get_decision_center_summary(mode="PAPER")
    text = f"{summary['synthesis_text']} {summary['next_milestone']} {summary['overall_status']}"

    # 1. No emojis
    emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
    assert not emoji_pattern.search(text)

    # 2. No forbidden fake-certainty words
    forbidden = ["guaranteed", "safe", "will make money", "certain", "proven to work", "100% win rate"]
    for word in forbidden:
        assert not re.search(r"\b" + re.escape(word) + r"\b", text.lower())

