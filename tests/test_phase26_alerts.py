"""
Unit tests for Phase 26 — Event-Based Alert Engine, Severities, Explainability, and Acknowledgement.
"""

import pytest
from xauusd_alert_engine import XAUUSDAlertEngine


def test_log_and_query_alerts():
    event_id = XAUUSDAlertEngine.log_event({
        "event_type": "EXPECTANCY_DRIFT",
        "severity": "WARNING",
        "metric": "Forward Expectancy",
        "observed_value": 0.41,
        "baseline_value": 0.637,
        "threshold": 0.45,
        "explanation": "Forward expectancy point estimate is currently +0.41R.",
        "recommended_action": "Monitor next 10 forward observations."
    })
    assert event_id.startswith("EVT_")

    events = XAUUSDAlertEngine.get_events(severity_filter="WARNING")
    assert any(e["event_id"] == event_id for e in events)


def test_alert_acknowledgement():
    event_id = XAUUSDAlertEngine.log_event({
        "event_type": "SAMPLE_SIZE_PROGRESS",
        "severity": "INFORMATION",
        "metric": "Sample Size N",
        "observed_value": 30,
        "baseline_value": 0,
        "threshold": 30,
        "explanation": "Stage 1 sample size milestone achieved.",
        "recommended_action": "Continue streaming."
    })
    
    ack_res = XAUUSDAlertEngine.acknowledge_alert(event_id)
    assert ack_res is True

    # Confirm event is preserved in database with acknowledged status
    events = XAUUSDAlertEngine.get_events(acknowledged_filter="ACKNOWLEDGED")
    target = next((e for e in events if e["event_id"] == event_id), None)
    assert target is not None
    assert target["acknowledged"] == 1
    assert target["event_type"] == "SAMPLE_SIZE_PROGRESS"


def test_alert_explainability_payload():
    event = {
        "event_id": "EVT_TEST_123",
        "event_type": "TIMEOUT_RATE_ELEVATED",
        "severity": "WARNING",
        "metric": "1M Limit Timeout Rate",
        "observed_value": 32.0,
        "baseline_value": 8.5,
        "threshold": 25.0,
        "explanation": "Limit order timeout rate reached 32.0%.",
        "recommended_action": "Investigate spread and fill slippage.",
        "acknowledged": 0
    }
    exp = XAUUSDAlertEngine.explain_alert(event)
    assert "what_happened" in exp
    assert "how_bad_is_it" in exp
    assert "why_does_it_matter" in exp
    assert "what_caused_the_alert" in exp
    assert "what_should_i_do" in exp
    assert "WATCH / WARNING" in exp["how_bad_is_it"]
    assert "Limit Order" in exp["why_does_it_matter"] or "microstructure" in exp["why_does_it_matter"].lower()
