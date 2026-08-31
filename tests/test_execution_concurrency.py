"""
Tests for Execution Concurrency & True Idempotency (Phase 12B)
Verifies:
1. 20 concurrent threads submitting the exact same signal_id produce exactly 1 claim and 19 blocked duplicates.
2. In-flight risk reservations prevent simultaneous racing requests from exceeding portfolio risk limits.
"""

import threading
import time
import uuid
import pytest
import database
import execution_pipeline
from execution_pipeline import CanonicalExecutionRequest, ExecutionState


import market_data

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Ensure clean test environment."""
    database.init_db()
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "PAPER")
    database.set_setting("MAX_TRADE_RISK_PCT", "25.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "50.0")
    database.set_setting("MAX_SYMBOL_EXPOSURE", "100")
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "100.0")
    monkeypatch.setattr(market_data, "get_latest_price", lambda s: 1.0850)
    monkeypatch.setattr(market_data, "get_latest_tick", lambda s: {"bid": 1.0848, "ask": 1.0850})
    monkeypatch.setattr(market_data, "get_market_health", lambda s, tf: {"status": "HEALTHY"})
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM open_positions")
    conn.commit()
    conn.close()


def test_20_concurrent_threads_same_signal_id():
    """
    Submits 20 simultaneous threads with the exact same signal_id.
    Must result in exactly 1 success / claim and 19 DUPLICATE_SIGNAL rejections.
    """
    shared_signal_id = f"RACE_TEST_{uuid.uuid4().hex[:8]}"
    results = []
    threads = []

    def worker():
        req = CanonicalExecutionRequest(
            signal_id=shared_signal_id,
            symbol="EURUSD",
            side="BUY",
            quantity=0.01,
            requested_entry=1.0850,
            stop_loss=1.0800,
            take_profit=1.0950,
            broker="PAPER",
            mode="PAPER",
            source="CONCURRENCY_TEST",
            strategy="RaceTest"
        )
        res = execution_pipeline.submit_order(req)
        results.append(res)

    # Spawn 20 threads simultaneously
    for _ in range(20):
        t = threading.Thread(target=worker)
        threads.append(t)

    # Launch all threads at the exact same instant
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 20

    success_claims = [r for r in results if r.get("status") == "success"]
    duplicate_claims = [r for r in results if "DUPLICATE_SIGNAL" in r.get("message", "")]

    # Exactly 1 success, exactly 19 duplicates
    assert len(success_claims) == 1, f"Expected 1 claim, got {len(success_claims)}"
    assert len(duplicate_claims) == 19, f"Expected 19 duplicates, got {len(duplicate_claims)}"


def test_concurrent_portfolio_risk_reservation():
    """
    Verifies that simultaneous distinct signals reserve risk in-flight
    and block concurrent requests that would exceed the total portfolio risk limit.
    """
    # Setup initial risk limits
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "PAPER")
    database.set_setting("MAX_TRADE_RISK_PCT", "25.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "6.0")
    database.set_setting("MAX_SYMBOL_EXPOSURE", "100")

    # Order 1: Consumes ~4.6% risk ($500 on $10,000)
    sig1 = f"RISK_RACE_1_{uuid.uuid4().hex[:6]}"
    sig2 = f"RISK_RACE_2_{uuid.uuid4().hex[:6]}"

    # Manually hold a risk reservation for sig1
    execution_pipeline.reserve_risk(sig1, 4.5)

    try:
        # Order 2 proposes 3.0% risk ($300 on $10,000) -> Total would be 4.5% (reserved) + 3.0% = 7.5% > 6.0% Max Total Risk
        req2 = CanonicalExecutionRequest(
            signal_id=sig2,
            symbol="EURUSD",
            side="BUY",
            quantity=0.60,  # 50 pips * 0.60 * 100k = $300 = 3.0%
            requested_entry=1.0850,
            stop_loss=1.0800,
            take_profit=1.0950,
            broker="PAPER",
            mode="PAPER"
        )
        res2 = execution_pipeline.submit_order(req2)
        assert res2.get("status") == "rejected"
        assert "TOTAL_RISK_LIMIT" in res2.get("message", "")
    finally:
        # Cleanup
        execution_pipeline.release_risk(sig1)
