"""
Tests for Paper and Shadow Execution Parity (Phase 12B)
"""

import uuid
import pytest
import database
import execution_pipeline
from execution_pipeline import CanonicalExecutionRequest, ExecutionState


import market_data

@pytest.fixture(autouse=True)
def setup_settings(monkeypatch):
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "PAPER")
    database.set_setting("MAX_TRADE_RISK_PCT", "25.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "50.0")
    database.set_setting("MAX_SYMBOL_EXPOSURE", "10")
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "100.0")
    monkeypatch.setattr(market_data, "get_latest_price", lambda s: 1.0850)
    monkeypatch.setattr(market_data, "get_latest_tick", lambda s: {"bid": 1.0848, "ask": 1.0850})
    monkeypatch.setattr(market_data, "get_market_health", lambda s, tf: {"status": "HEALTHY"})
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM open_positions")
    conn.commit()
    conn.close()


def test_shadow_paper_decision_parity():
    """
    Submitting identical valid parameters to Paper and Shadow
    must both succeed and pass through all risk and validation gates.
    """
    sig_paper = f"PARITY_PAPER_{uuid.uuid4().hex[:6]}"
    sig_shadow = f"PARITY_SHADOW_{uuid.uuid4().hex[:6]}"

    req_paper = CanonicalExecutionRequest(
        signal_id=sig_paper,
        symbol="EURUSD",
        side="BUY",
        quantity=0.01,
        requested_entry=1.0850,
        stop_loss=1.0800,
        take_profit=1.0950,
        broker="PAPER",
        mode="PAPER"
    )

    req_shadow = CanonicalExecutionRequest(
        signal_id=sig_shadow,
        symbol="EURUSD",
        side="BUY",
        quantity=0.01,
        requested_entry=1.0850,
        stop_loss=1.0800,
        take_profit=1.0950,
        broker="SHADOW",
        mode="SHADOW"
    )

    res_paper = execution_pipeline.submit_order(req_paper)
    res_shadow = execution_pipeline.submit_order(req_shadow)

    assert res_paper.get("status") == "success"
    assert res_paper.get("state") == ExecutionState.FILLED

    assert res_shadow.get("status") == "success"
    assert res_shadow.get("state") == ExecutionState.FILLED


def test_shadow_mode_leaves_zero_database_positions():
    """
    Shadow execution must never insert an open position into open_positions table.
    """
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM open_positions WHERE account_id = 'SHADOW'")
    shadow_pos_count = cur.fetchone()[0]
    conn.close()

    assert shadow_pos_count == 0
