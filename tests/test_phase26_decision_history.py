"""
Unit tests for Phase 26 — Decision History Append-Only Repository & Timeline.
"""

import pytest
from xauusd_decision_history import XAUUSDDecisionHistory


def test_record_decision_snapshot_append_only():
    snap_id = XAUUSDDecisionHistory.record_decision_snapshot({
        "stage": "Stage 1 (Preliminary Indication)",
        "forward_n": 35,
        "expectancy_r": 0.52,
        "ci_lower": 0.20,
        "ci_upper": 0.84,
        "drawdown_r": 2.8,
        "execution_health": "OPTIMAL",
        "drift_status": "DISTRIBUTIONALLY CONSISTENT",
        "integrity_status": "PASS",
        "overall_decision": "COLLECTING FORWARD DATA",
        "next_action": "Stream toward Stage 2 (N = 50)."
    })
    assert snap_id.startswith("DEC_")

    timeline = XAUUSDDecisionHistory.get_decision_timeline(limit=10)
    assert len(timeline) > 0
    target = next((d for d in timeline if d["decision_id"] == snap_id), None)
    assert target is not None
    assert target["forward_n"] == 35
    assert target["expectancy_r"] == 0.52
    assert target["stage"] == "Stage 1 (Preliminary Indication)"


def test_decision_timeline_ordering():
    snap_a = XAUUSDDecisionHistory.record_decision_snapshot({
        "stage": "Stage 0", "forward_n": 10, "expectancy_r": 0.3, "ci_lower": -0.1, "ci_upper": 0.7,
        "drawdown_r": 1.0, "execution_health": "OPTIMAL", "drift_status": "INSUFFICIENT DATA",
        "integrity_status": "PASS", "overall_decision": "DATA ACCUMULATION", "next_action": "Collect."
    })
    snap_b = XAUUSDDecisionHistory.record_decision_snapshot({
        "stage": "Stage 0", "forward_n": 15, "expectancy_r": 0.4, "ci_lower": 0.0, "ci_upper": 0.8,
        "drawdown_r": 1.5, "execution_health": "OPTIMAL", "drift_status": "INSUFFICIENT DATA",
        "integrity_status": "PASS", "overall_decision": "DATA ACCUMULATION", "next_action": "Collect."
    })
    
    timeline = XAUUSDDecisionHistory.get_decision_timeline(limit=5)
    # Most recent snapshot should be at the top
    assert timeline[0]["decision_id"] == snap_b or timeline[0]["created_at"] >= timeline[1]["created_at"]
