"""
Unit tests for Phase 25 — Real-time Live MTF State Engine.
Tests all 5 MTF layers (1D, 4H, 15M, 5M, 1M) and the master trade decision synthesis.
"""

import pytest
from xauusd_live_state_engine import XAUUSDLiveMTFStateEngine


def test_1d_macro_bias_bullish_and_bearish():
    # Bullish
    bias_bull = XAUUSDLiveMTFStateEngine.get_1d_macro_bias(
        "XAUUSD",
        custom_override={"state": "BULLISH", "ema20": 2410.0, "ema50": 2380.0, "last_close": 2415.0}
    )
    assert bias_bull["state"] == "BULLISH"
    assert bias_bull["status"] == "PASS"
    assert "permits LONG" in bias_bull["explanation"]

    # Bearish
    bias_bear = XAUUSDLiveMTFStateEngine.get_1d_macro_bias(
        "XAUUSD",
        custom_override={"state": "BEARISH", "ema20": 2380.0, "ema50": 2410.0, "last_close": 2375.0}
    )
    assert bias_bear["state"] == "BEARISH"
    assert bias_bear["status"] == "PASS"
    assert "permits SHORT" in bias_bear["explanation"]

    # Neutral
    bias_neut = XAUUSDLiveMTFStateEngine.get_1d_macro_bias(
        "XAUUSD",
        custom_override={"state": "NEUTRAL"}
    )
    assert bias_neut["state"] == "NEUTRAL"
    assert bias_neut["status"] == "BLOCKED"
    assert "No intraday setup can proceed" in bias_neut["explanation"]


def test_4h_dol_evaluation_and_2r_minimum():
    # 2R Satisfied (Entry 2400, SL 2398 -> Risk 2.0; DOL 2406 -> Reward 6.0 -> 3.0R)
    dol_pass = XAUUSDLiveMTFStateEngine.get_4h_dol(
        "XAUUSD",
        planned_entry=2400.0,
        planned_sl=2398.0,
        custom_override={"dol_type": "PDH", "dol_price": 2406.0}
    )
    assert dol_pass["status"] == "PASS"
    assert dol_pass["meets_min_2r"] is True
    assert dol_pass["r_potential"] == 3.0
    assert "satisfying the minimum 2.0R" in dol_pass["explanation"]

    # 2R Rejected (Entry 2400, SL 2398 -> Risk 2.0; DOL 2403 -> Reward 3.0 -> 1.5R)
    dol_fail = XAUUSDLiveMTFStateEngine.get_4h_dol(
        "XAUUSD",
        planned_entry=2400.0,
        planned_sl=2398.0,
        custom_override={"dol_type": "4H_FVG", "dol_price": 2403.0}
    )
    assert dol_fail["status"] == "REJECTED"
    assert dol_fail["meets_min_2r"] is False
    assert dol_fail["r_potential"] == 1.5
    assert "requires at least 2.0R" in dol_fail["explanation"]


def test_15m_setup_checklist_evaluation():
    # Full Pass Checklist
    cl_pass = XAUUSDLiveMTFStateEngine.get_15m_setup_checklist(
        "XAUUSD",
        custom_checklist={
            "liquidity_sweep_detected": True,
            "sweep_closed_inside_range": True,
            "mss_confirmed": True,
            "displacement_confirmed": True,
            "body_ratio_ge_65": True,
            "fvg_formed": True,
            "fvg_size_ge_half_atr": True,
            "setup_expired": False,
            "setup_invalidated": False
        }
    )
    assert cl_pass["overall_status"] == "PASS"
    assert cl_pass["all_passed"] is True
    assert len(cl_pass["items"]) == 9

    # Partial / Failed Checklist
    cl_fail = XAUUSDLiveMTFStateEngine.get_15m_setup_checklist(
        "XAUUSD",
        custom_checklist={
            "liquidity_sweep_detected": True,
            "sweep_closed_inside_range": False,
            "mss_confirmed": False,
            "displacement_confirmed": False,
            "body_ratio_ge_65": False,
            "fvg_formed": False,
            "fvg_size_ge_half_atr": False,
            "setup_expired": False,
            "setup_invalidated": False
        }
    )
    assert cl_fail["all_passed"] is False


def test_5m_confirmation_and_1m_precision_entry():
    # 5M Confirmed
    c5m = XAUUSDLiveMTFStateEngine.get_5m_confirmation(
        "XAUUSD",
        custom_override={"confirmed": True, "bars_since_mss": 2, "quality": "HIGH"}
    )
    assert c5m["status"] == "PASS"
    assert c5m["is_expired"] is False

    # 5M Expired
    c5m_exp = XAUUSDLiveMTFStateEngine.get_5m_confirmation(
        "XAUUSD",
        custom_override={"confirmed": True, "bars_since_mss": 5, "quality": "HIGH"}
    )
    assert c5m_exp["status"] == "EXPIRED"
    assert c5m_exp["is_expired"] is True

    # 1M Waiting
    c1m = XAUUSDLiveMTFStateEngine.get_1m_precision_entry(
        "XAUUSD",
        custom_override={"state": "WAITING", "limit_price": 2400.50, "sl_price": 2398.50, "timer_min_remaining": 12}
    )
    assert c1m["state"] == "WAITING"
    assert c1m["planned_rr"] > 0
    assert "Expiration timer: 12 min" in c1m["explanation"]


def test_master_trade_decision_states():
    # Check all required states synthesize clear plain-language explanations
    states = [
        "NO SETUP", "WATCHING", "SETUP DEVELOPING", "WAITING FOR CONFIRMATION",
        "WAITING FOR 1M ENTRY", "LIMIT ORDER ACTIVE", "PAPER TRADE ACTIVE",
        "SHADOW SIGNAL ACTIVE", "SETUP INVALIDATED", "ORDER EXPIRED", "TRADE COMPLETED"
    ]
    for s in states:
        dec = XAUUSDLiveMTFStateEngine.get_current_trade_decision("XAUUSD", custom_state=s)
        assert dec["state"] == s
        assert len(dec["explanation"]) > 10
        assert "DISABLED PERMANENTLY" in dec["live_automation"]


def test_complete_live_market_state_compilation():
    comp = XAUUSDLiveMTFStateEngine.get_complete_live_market_state("XAUUSD")
    assert "decision" in comp
    assert "layer_1d" in comp
    assert "layer_4h" in comp
    assert "layer_15m" in comp
    assert "layer_5m" in comp
    assert "layer_1m" in comp
