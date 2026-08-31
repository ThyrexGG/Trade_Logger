"""
Unit tests for Phase 25 — Rejection Hierarchy, Trade Entry Decision Trails, and Failure Attribution.
"""

import pytest
import research_explanations
from research_explanations import ExplainableResearchClassifier, ExecutionFailureClassifier


def test_all_15_rejection_reason_codes():
    rejection_codes = [
        "DAILY_BIAS_NEUTRAL", "DAILY_BIAS_OPPOSITE", "NO_VALID_DOL", "DOL_DISTANCE_BELOW_2R",
        "NO_LIQUIDITY_SWEEP", "SWEEP_NOT_CONFIRMED", "MSS_NOT_CONFIRMED", "DISPLACEMENT_TOO_WEAK",
        "FVG_TOO_SMALL", "SETUP_EXPIRED", "5M_CONFIRMATION_MISSING", "NO_1M_FVG",
        "1M_ENTRY_EXPIRED", "SWING_INVALIDATED", "RISK_GATE_REJECTED"
    ]
    for code in rejection_codes:
        res = ExplainableResearchClassifier.explain_entry_rejection(code, details={"rr_available": 1.7})
        assert res["reason_code"] == code
        assert len(res["what_failed"]) > 0
        assert len(res["why_it_failed"]) > 0
        assert "Rule" in res["rule_triggered"]
        assert "TRADE REJECTED" in res["summary_text"]


def test_execution_failure_classifier_separates_strategy_from_execution():
    # Strategy Failure (Stop Loss Hit)
    sf = ExecutionFailureClassifier.classify_failure("STRATEGY_LOSS")
    assert sf["category"] == "STRATEGY FAILURE"
    assert sf["is_execution_issue"] is False
    assert "Stop Loss" in sf["meaning"]
    assert "standard trade outcome" in sf["action_guidance"]

    # Execution Failure (1M Limit Timeout)
    ef = ExecutionFailureClassifier.classify_failure("LIMIT_TIMEOUT")
    assert ef["category"] == "EXECUTION FAILURE"
    assert ef["is_execution_issue"] is True
    assert "limit order execution friction" in ef["meaning"]
    assert "FUTURE_RESEARCH_QUEUE" in ef["action_guidance"]

    # Execution Friction (Excessive Spread)
    ef_spread = ExecutionFailureClassifier.classify_failure("SPREAD_WIDE")
    assert ef_spread["category"] == "EXECUTION FRICTION"
    assert ef_spread["is_execution_issue"] is True


def test_explain_trade_entry_decision_trail():
    trade_data = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "bias_1d": "Bullish Trend (Above 20/50 EMA)",
        "dol_4h": "PDH Target (2415.50 / 3.2R)",
        "setup_15m": "Asian Low Swept + MSS Close",
        "conf_5m": "5M FVG Confirmed",
        "entry_1m": "Limit filled at 2400.50",
        "sl_pips": 14.5,
        "target_r": 3.2
    }
    trail_res = ExplainableResearchClassifier.explain_trade_entry(trade_data)
    assert trail_res["symbol"] == "XAUUSD"
    assert trail_res["direction"] == "LONG"
    assert len(trail_res["decision_trail"]) == 8
    assert all(t["status"] == "PASS" for t in trail_res["decision_trail"])
    assert "FINAL DECISION: PAPER/SHADOW ENTRY APPROVED" in trail_res["final_decision"]
