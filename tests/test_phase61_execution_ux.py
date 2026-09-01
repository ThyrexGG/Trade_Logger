# -*- coding: utf-8 -*-
"""
Phase 61 - Test Execution Panel UX, Risk Calculations & Live Safety Barrier
"""
import pytest
import risk_gateway


def test_pre_trade_risk_calculation_integrity():
    """Verify pre-trade risk calculation produces lot sizes, worst-case risk, and R:R ratio."""
    res = risk_gateway.calculate_pre_trade_risk_preview(
        symbol="XAUUSD",
        side="BUY",
        entry_price=2400.0,
        stop_loss=2390.0,
        take_profit_1=2425.0,
        requested_risk_pct=1.0,
        account_balance=10000.0
    )
    assert res["is_valid"] is True
    assert res["calculated_lot_size"] > 0
    assert res["actual_risk_usd"] > 0
    assert res["reward_tp1_usd"] > 0
    assert "risk_reward_ratio" in res
    assert len(str(res["risk_reward_ratio"])) > 0


def test_invalid_sl_detected():
    """Verify that invalid SL relative to entry triggers validation error."""
    res = risk_gateway.calculate_pre_trade_risk_preview(
        symbol="XAUUSD",
        side="BUY",
        entry_price=2400.0,
        stop_loss=2410.0,  # invalid for BUY
        take_profit_1=2425.0,
        requested_risk_pct=1.0,
        account_balance=10000.0
    )
    assert res["is_valid"] is False
    assert len(res["errors"]) >= 1
