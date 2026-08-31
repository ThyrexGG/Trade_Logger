"""
Tests for Price-Side Correctness and Execution Price Deviation Gate (Phase 12B)
"""

import uuid
import pytest
import database
import execution_pipeline
from execution_pipeline import CanonicalExecutionRequest, ExecutionState


def test_price_deviation_gate_rejection(monkeypatch):
    """
    If executable price is significantly deviated from requested reference entry,
    the execution pipeline must fail-closed and reject with PRICE_DEVIATION_EXCEEDED.
    """
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "PAPER")
    database.set_setting("MAX_TRADE_RISK_PCT", "25.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "50.0")
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "0.50") # 0.50% max deviation

    # Mock market data returning ask=1.1200 when requested entry is 1.0850 (deviation = ~3.2% > 0.50%)
    import market_data
    monkeypatch.setattr(market_data, "get_latest_tick", lambda sym: {"bid": 1.1198, "ask": 1.1200})

    sig_id = f"PRICE_DEV_TEST_{uuid.uuid4().hex[:6]}"
    req = CanonicalExecutionRequest(
        signal_id=sig_id,
        symbol="EURUSD",
        side="BUY",
        quantity=0.01,
        requested_entry=1.0850,
        stop_loss=1.0800,
        take_profit=1.0950,
        broker="PAPER",
        mode="PAPER"
    )

    res = execution_pipeline.submit_order(req)
    assert res.get("status") == "rejected"
    assert "PRICE_DEVIATION_EXCEEDED" in res.get("message", "")
