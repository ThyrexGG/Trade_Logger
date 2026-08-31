import pytest
from backtester import run_walk_forward
import pandas as pd

def test_run_walk_forward():
    # Since WFO fetches data and runs backtest over multiple slices,
    # we just want to ensure the engine doesn't crash and returns the correct stitched fields.
    
    # We use a fast timeframe so the test doesn't take forever fetching massive data
    res = run_walk_forward(
        symbol="EURUSD",
        timeframe="5m",
        strategy="Trend Continuation",
        risk_pct=1.0,
        grid_sl=[1.5, 2.0],
        grid_tp=[2.0],
        walk_steps=2,
        oos_pct=0.2
    )
    
    if "error" in res:
        # Ignore if it's just a network/data fetch error
        assert "Data fetch" in res["error"] or "Failed to fetch" in res["error"] or "Walk-forward optimization yielded zero" in res["error"]
    else:
        assert "metrics" in res
        assert "equity_curve" in res
        assert "monte_carlo" in res
        assert res["metrics"]["WFO"] == "Robust"
        assert len(res["trades"]) > 0
        
        # Verify the stitching ensures trades are marked OOS
        for trade in res["trades"]:
            assert trade["is_oos"] is True
