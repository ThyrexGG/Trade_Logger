"""
Phase 40 — Daily Research Review & Non-Causal Attribution Test Suite
Validates 5-pillar daily review and non-causal attribution language.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_event_traceability import (
    NonCausalAttributionEngine,
    StructuredDailyReviewSynthesizer,
)


def test_non_causal_attribution_language():
    """Validates attribution returns honest uncertainty language and disclaimers."""
    obs_time = datetime(2026, 9, 1, 12, 35, 0, tzinfo=timezone.utc)
    obs = {"signal_id": "OBS_ATTR_001", "timestamp": obs_time.isoformat()}
    events = [
        {
            "event_name": "US CPI",
            "scheduled_timestamp": "2026-09-01T12:30:00+00:00"
        }
    ]

    attr = NonCausalAttributionEngine.evaluate_observation_attribution(obs, events)

    assert "HIGH PROXIMITY" in attr["attribution_tag"]
    assert "Causality not established" in attr["explanation"]
    assert "Observational context only" in attr["disclaimer"]


def test_structured_daily_review_five_pillars():
    """Validates 5-pillar daily review synthesis."""
    target_dt = date(2026, 9, 1)
    rev = StructuredDailyReviewSynthesizer.synthesize_daily_review(target_dt)

    assert "market_pillar" in rev
    assert "news_pillar" in rev
    assert "strategy_pillar" in rev
    assert "quality_pillar" in rev
    assert "research_interpretation" in rev
    assert rev["strategy_pillar"]["contract_status"] == "FROZEN (PHASE 21 LOCKED)"
    assert rev["strategy_pillar"]["live_automation"] == "DISABLED PERMANENTLY"
