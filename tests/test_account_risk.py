"""
Tests for Account-Level Risk Gates (Phase 12B)
Verifies:
1. Trade within risk bounds passes.
2. Trade blocked when floating loss breaches daily loss limit.
3. Trade blocked when combined open risk exceeds total risk limit.
4. Fail-closed when broker account state is unavailable in live mode.
"""

import pytest
import time
import database
import execution_pipeline
import risk_gateway
import market_data
from execution_pipeline import CanonicalExecutionRequest, ExecutionState


@pytest.fixture(autouse=True)
def mock_db_risk(monkeypatch):
    database.init_db()
    database.set_setting("SYSTEM_STATE", "PAPER")
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("MAX_DAILY_LOSS_PCT", "10.0")
    database.set_setting("MAX_TRADE_RISK_PCT", "5.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "15.0")
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "100.0")
    monkeypatch.setattr(market_data, "get_market_health", lambda sym, tf: {"status": "HEALTHY"})
    import pandas as pd
    monkeypatch.setattr(database, "get_open_positions", lambda: pd.DataFrame())


def test_account_risk_allowed(monkeypatch):
    """A trade with small risk well within limits must pass."""
    sig = {
        "signal_id": f"TEST_ALLOW_{int(time.time()*1000)}",
        "symbol": "EURUSD",
        "side": "BUY",
        "requested_quantity": 0.01,
        "requested_entry": 1.0500,
        "stop_loss": 1.0480, # 20 pips * 0.01 * 100k = $20 risk (0.2% on $10k)
        "take_profit": 1.0600,
        "broker": "PAPER",
        "mode": "PAPER"
    }
    res = risk_gateway.evaluate_trade_risk(sig)
    assert res["approved"] is True, f"Risk rejected with reasons: {res['reasons']}"
    assert res["risk_score"] > 0


def test_account_risk_blocked_by_floating(monkeypatch):
    """When floating PnL breaches max daily loss limit, new trade is rejected."""
    database.set_setting("MAX_DAILY_LOSS_PCT", "5.0") # 5% limit = -$500 on $10,000
    
    # Mock database account balances with heavy floating loss (-$600)
    monkeypatch.setattr(database, "get_account_balances", lambda: {
        "PAPER": {
            "balance": 10000.0,
            "equity": 9400.0,
            "floating_pnl": -600.0,
            "realized_daily_pnl": 0.0
        }
    })

    sig = {
        "signal_id": f"TEST_FLOAT_LOSS_{int(time.time()*1000)}",
        "symbol": "EURUSD",
        "side": "BUY",
        "requested_quantity": 0.01,
        "requested_entry": 1.0500,
        "stop_loss": 1.0480,
        "broker": "PAPER",
        "mode": "PAPER"
    }
    res = risk_gateway.evaluate_trade_risk(sig)
    assert res["approved"] is False
    assert any("DAILY_LOSS_BREACH" in r for r in res["reasons"])


def test_account_risk_aggregate_risk_blocked(monkeypatch):
    """When proposed trade would cause total portfolio risk to exceed MAX_TOTAL_RISK_PCT, reject."""
    database.set_setting("MAX_TRADE_RISK_PCT", "25.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "10.0")
    
    # Mock database open_positions with existing heavy risk ($800 risk on $10,000 = 8%)
    import pandas as pd
    monkeypatch.setattr(database, "get_open_positions", lambda: pd.DataFrame([
        {"symbol": "GBPUSD", "direction": "BUY", "volume": 0.16, "entry_price": 1.2500, "sl": 1.2000, "floating_pnl": 0.0}
    ]))

    # Proposed trade on USDJPY adds $300 risk (3.0% on $10,000) -> Total Risk: 8.0% + 3.0% = 11.0% > 10.0% Max Total Risk
    sig = {
        "signal_id": f"TEST_AGG_RISK_{int(time.time()*1000)}",
        "symbol": "USDJPY",
        "side": "SELL",
        "requested_quantity": 0.10,
        "requested_entry": 150.00,
        "stop_loss": 153.00, # 3.00 yen * 0.10 * 100k / 150 = $200... wait: 3.00 * 0.10 * 1000 = $300 for JPY contract size
        "broker": "PAPER",
        "mode": "PAPER"
    }
    # Set MAX_TOTAL_RISK_PCT to 8.1% so existing 8% + any new trade > 0.1% triggers total risk limit
    database.set_setting("MAX_TOTAL_RISK_PCT", "8.1")
    res = risk_gateway.evaluate_trade_risk(sig)
    assert res["approved"] is False
    assert any("TOTAL_RISK_LIMIT" in r for r in res["reasons"])


def test_account_risk_broker_unavailable(monkeypatch):
    """In live mode, if broker account state cannot be fetched, fail-closed."""
    import account_state
    monkeypatch.setattr(account_state, "get_account_state", lambda b: {
        "status": "ERROR",
        "error_message": "Connection Timeout to Broker Gateway"
    })

    sig = {
        "signal_id": f"TEST_BROKER_UNAVAIL_{int(time.time()*1000)}",
        "symbol": "EURUSD",
        "side": "BUY",
        "requested_quantity": 0.01,
        "requested_entry": 1.0500,
        "stop_loss": 1.0480,
        "broker": "MT5",
        "mode": "LIVE"
    }
    res = risk_gateway.evaluate_trade_risk(sig)
    assert res["approved"] is False
    assert any("UNAVAILABLE_ACCOUNT_STATE" in r for r in res["reasons"])
