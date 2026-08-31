import pytest
import os
import time
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import portfolio_risk
import paper_simulator
import analytics
import database
import pandas as pd

def test_portfolio_risk_max_exposure():
    # Mock account state to return 2 open positions for EURUSD
    mock_state = {
        "status": "success",
        "equity": 10000.0,
        "total_open_risk": 500.0,
        "open_positions": [
            {"symbol": "EURUSD", "direction": "BUY"},
            {"symbol": "EURUSD", "direction": "BUY"}
        ]
    }
    with patch("account_state.get_account_state", return_value=mock_state):
        # Third EURUSD position should be rejected
        res = portfolio_risk.get_portfolio_risk_status("MT5", "EURUSD", "BUY", 100.0)
        assert res["is_valid"] is False
        assert "PORTFOLIO EXPOSURE" in res["error"]

def test_paper_simulator_fill():
    # Mock market data price (must use create=True since market_data doesn't actually have get_latest_price yet)
    with patch("paper_simulator.market_data.get_latest_price", return_value=1.10000, create=True):
        # Mock database connection to prevent real inserts
        with patch("database.get_connection") as mock_conn:
            res = paper_simulator.execute_paper_order("EURUSD", "BUY", 0.1, 1.10000, sl=1.09000, tp=1.11000)
            assert res["status"] == "success"
            # Spread is 0.00015, Slippage is 0.00005. Buy means price goes up (penalized).
            # Expected Fill: 1.10000 + 0.00015 + 0.00005 = 1.1002
            assert abs(res["execution_price"] - 1.1002) < 0.000001
            assert res["order_id"].startswith("PAPER_")

def test_signal_attribution():
    signals = pd.DataFrame([
        {"order_id": "POS_123", "setup_type": "London Sweep", "confluence_score": 5},
        {"order_id": "POS_456", "setup_type": "London Sweep", "confluence_score": 5}
    ])
    trades = pd.DataFrame([
        {"trade_id": "TRADE_123", "net_profit": 500.0},
        {"trade_id": "TRADE_456", "net_profit": -100.0}
    ])
    
    res = analytics.calculate_liquidity_performance(signals, trades)
    assert "London Sweep" in res
    assert res["London Sweep"]["count"] == 2
    assert res["London Sweep"]["win_rate"] == 50.0
    # Expectancy: (0.5 * 500) - (0.5 * 100) = 250 - 50 = 200
    assert res["London Sweep"]["expectancy"] == 200.0
