"""
Phase 53 — Tests for Docked Execution Panel & Risk Calculations
"""

import pytest
import risk_gateway


def test_pre_trade_risk_calculation_integration():
    res = risk_gateway.calculate_pre_trade_risk_preview(
        symbol="XAUUSD",
        side="BUY",
        entry_price=2400.0,
        stop_loss=2395.0,
        take_profit_1=2415.0,
        requested_risk_pct=1.0,
        account_balance=10000.0
    )
    assert res["is_valid"] is True
    assert res["calculated_lot_size"] > 0
    assert res["actual_risk_pct"] <= 1.0
    assert "1:" in str(res["risk_reward_ratio"])


def test_invalid_negative_price_rejected():
    res = risk_gateway.calculate_pre_trade_risk_preview(
        symbol="XAUUSD",
        side="BUY",
        entry_price=-2400.0,
        stop_loss=2395.0,
        take_profit_1=2415.0,
        requested_risk_pct=1.0,
        account_balance=10000.0
    )
    assert res["is_valid"] is False
    assert len(res["errors"]) > 0
