"""
Unit tests for Phase 24 Entry Rejections, Entry Approvals, MTF Stages & Risk Concepts.
"""

import pytest
from research_explanations import ExplainableResearchClassifier


def test_entry_rejection_catalog_all_codes():
    """Verify that all predefined entry rejection scenarios return what failed, why, and rule triggered."""
    rejection_codes = [
        "NO_DAILY_BIAS",
        "NO_VALID_4H_DOL",
        "DOL_BELOW_2R",
        "NO_LIQUIDITY_SWEEP",
        "MSS_NOT_CONFIRMED",
        "DISPLACEMENT_TOO_WEAK",
        "FVG_TOO_SMALL",
        "CONFIRMATION_5M_MISSING",
        "NO_1M_FVG_FOUND",
        "LIMIT_ORDER_EXPIRED",
        "SWING_INVALIDATED",
        "RISK_GATE_REJECTED"
    ]
    
    for code in rejection_codes:
        res = ExplainableResearchClassifier.explain_entry_rejection(code, {"rr_available": 1.4})
        assert res["reason_code"] == code
        assert "what_failed" in res and len(res["what_failed"]) > 0
        assert "why_it_failed" in res and len(res["why_it_failed"]) > 0
        assert "rule_triggered" in res and len(res["rule_triggered"]) > 0
        assert "REJECTED" in res["status"]


def test_entry_approval_breakdown():
    """Verify that approved entries provide a complete multi-timeframe explanation."""
    trade_info = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "bias_1d": "Bullish Trend (Price above 20/50 EMA)",
        "dol_4h": "PDH Target (2420.00 / 3.5R)",
        "setup_15m": "Asian Low Swept + Confirmed MSS Close",
        "conf_5m": "5M FVG Formed with Displacement",
        "entry_1m": "Limit filled at 2405.00",
        "sl_pips": 14.5,
        "target_r": 3.5
    }
    
    exp = ExplainableResearchClassifier.explain_trade_entry(trade_info)
    assert "WHY DID WE ENTER?" in exp["title"]
    assert exp["direction"] == "LONG"
    assert "1D" in exp["layer_1d"]
    assert "4H" in exp["layer_4h"]
    assert "15M" in exp["layer_15m"]
    assert "5M" in exp["layer_5m"]
    assert "1M" in exp["layer_1m"]
    assert "14.5" in exp["risk_spec"]
    assert exp["decision"] == "PAPER ORDER APPROVED & EXECUTED"


def test_mtf_stage_explainer():
    """Verify MTF stage explanations for 1D, 4H, 15M, 5M, 1M."""
    stages = ["1D", "4H", "15M", "5M", "1M"]
    for s in stages:
        exp_pass = ExplainableResearchClassifier.explain_mtf_stage(s, "PASS")
        assert exp_pass["status"] == "PASS"
        assert "purpose" in exp_pass and len(exp_pass["purpose"]) > 0
        assert "meaning" in exp_pass and len(exp_pass["meaning"]) > 0

        exp_wait = ExplainableResearchClassifier.explain_mtf_stage(s, "WAITING")
        assert exp_wait["status"] == "WAITING"


def test_risk_concepts_plain_language():
    """Verify that core risk parameters have plain-language educational definitions."""
    concepts = ExplainableResearchClassifier.explain_risk_concepts()
    assert "risk_per_trade" in concepts
    assert "r_multiple" in concepts
    assert "min_2r_rule" in concepts
    assert "structural_sl" in concepts
    assert "tight_sl_danger" in concepts

    for key, item in concepts.items():
        assert "title" in item
        assert "meaning" in item
        assert "why_important" in item
