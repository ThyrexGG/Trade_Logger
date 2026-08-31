import pytest
from backtester import run_monte_carlo

def test_monte_carlo_positive_expectancy():
    # Create 100 dummy trades with a slight edge
    trades = [{"pnl": 50.0} for _ in range(60)] + [{"pnl": -40.0} for _ in range(40)]
    
    res = run_monte_carlo(trades, initial_capital=10000.0, iterations=100, risk_of_ruin_level=0.5)
    
    assert "error" not in res
    assert res["iterations"] == 100
    assert res["risk_of_ruin_pct"] == 0.0 # With this edge, risk of ruin should be near 0
    assert "confidence_95_dd_pct" in res

def test_monte_carlo_negative_expectancy():
    # Create dummy trades with terrible edge
    trades = [{"pnl": 50.0} for _ in range(30)] + [{"pnl": -100.0} for _ in range(70)]
    
    res = run_monte_carlo(trades, initial_capital=1000.0, iterations=100, risk_of_ruin_level=0.1)
    
    assert "error" not in res
    assert res["risk_of_ruin_pct"] > 50.0 # Very likely to hit a 10% drawdown quickly
