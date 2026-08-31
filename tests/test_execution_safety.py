"""
Comprehensive Execution Safety & Security Test Suite (Phase 12B / 13)
Tests:
- Webhook HMAC / Secret authentication
- Replay & duplicate signal prevention
- Stale timestamp (>300s) and future timestamp rejection
- Geometry validation (SL/TP)
- Volume and lot step constraints
- Daily loss & floating PnL limits
- Emergency halt & kill switch
- Rate limiting on webhook endpoints
- Paper / Shadow / Live execution parity
"""

import pytest
import time
import uuid
from fastapi.testclient import TestClient
from server import app
import database
import execution_pipeline
import risk_gateway
import market_data
import account_state
from execution_pipeline import CanonicalExecutionRequest, ExecutionState

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_safety_environment(monkeypatch):
    database.init_db()
    database.set_setting("SYSTEM_STATE", "PAPER")
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("MAX_DAILY_LOSS_PCT", "5.0")
    database.set_setting("MAX_TRADE_RISK_PCT", "5.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "25.0")
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "100.0")
    database.set_setting("MAX_SYMBOL_EXPOSURE", "5")
    
    # Mock market health and ticks for consistent local tests
    monkeypatch.setattr(market_data, "get_market_health", lambda sym, tf: {"status": "HEALTHY"})
    monkeypatch.setattr(market_data, "get_latest_tick", lambda sym: {"bid": 1.0500, "ask": 1.0502})
    monkeypatch.setattr(market_data, "get_latest_price", lambda sym: 1.0500)
    
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM open_positions")
    cur.execute("DELETE FROM execution_orders")
    conn.commit()
    conn.close()


def test_1_invalid_webhook_secret(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "SUPER_SECRET_123")
    response = client.post("/api/webhook/tradingview", json={
        "secret": "WRONG_SECRET", "signal_id": f"SIG_{uuid.uuid4().hex[:8]}", "timestamp": time.time(),
        "symbol": "EURUSD", "direction": "BUY", "volume": 0.1
    })
    assert response.status_code == 401


def test_2_missing_secret():
    response = client.post("/api/webhook/tradingview", json={
        "signal_id": f"SIG_{uuid.uuid4().hex[:8]}", "timestamp": time.time(), "symbol": "EURUSD", "direction": "BUY", "volume": 0.1
    })
    assert response.status_code == 422 # Pydantic validation error


def test_3_expired_timestamp():
    res = execution_pipeline.submit_order(
        signal_id=f"STALE_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.1,
        timestamp=time.time() - 600, requested_entry=1.0500, stop_loss=1.0450
    )
    assert res["status"] in ["rejected", "error"]
    assert "STALE" in res["message"]


def test_4_future_timestamp():
    res = execution_pipeline.submit_order(
        signal_id=f"FUTURE_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.1,
        timestamp=time.time() + 100, requested_entry=1.0500, stop_loss=1.0450
    )
    assert res["status"] in ["rejected", "error"]
    assert "FUTURE" in res["message"]


def test_5_duplicate_signal():
    sig_id = f"DUP_{uuid.uuid4().hex[:8]}"
    res1 = execution_pipeline.submit_order(
        signal_id=sig_id, symbol="EURUSD", direction="BUY", volume=0.1, requested_entry=1.0500, stop_loss=1.0450, mode="PAPER"
    )
    assert res1["status"] == "success"
    
    # Second submission must be rejected atomically
    res2 = execution_pipeline.submit_order(
        signal_id=sig_id, symbol="EURUSD", direction="BUY", volume=0.1, requested_entry=1.0500, stop_loss=1.0450, mode="PAPER"
    )
    assert res2["status"] == "error"
    assert "DUPLICATE_SIGNAL" in res2["message"]


def test_6_malformed_json():
    response = client.post("/api/webhook/tradingview", content="NOT JSON")
    assert response.status_code == 422


def test_7_missing_required_fields():
    response = client.post("/api/webhook/tradingview", json={"secret": "changeme_in_production!"})
    assert response.status_code == 422


def test_8_invalid_direction():
    res = execution_pipeline.submit_order(
        signal_id=f"INV_DIR_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="HOLD", volume=0.1, requested_entry=1.0500
    )
    assert res["status"] == "rejected"
    assert "INVALID" in res["message"] or "Direction" in res["message"]


def test_9_unknown_symbol():
    res = execution_pipeline.submit_order(
        signal_id=f"UNK_SYM_{uuid.uuid4().hex[:8]}", symbol="RANDOMUNKNOWN123", direction="BUY", volume=0.1, requested_entry=1.0
    )
    assert res["status"] == "rejected"
    assert "UNKNOWN_SYMBOL" in res["message"]


def test_10_buy_sl_above_entry():
    res = execution_pipeline.submit_order(
        signal_id=f"BUY_SL_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.1, requested_entry=1.0500, stop_loss=1.0600
    )
    assert res["status"] == "rejected"
    assert "GEOMETRY_ERROR" in res["message"] or "below" in res["message"]


def test_11_sell_sl_below_entry():
    res = execution_pipeline.submit_order(
        signal_id=f"SELL_SL_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="SELL", volume=0.1, requested_entry=1.0500, stop_loss=1.0400
    )
    assert res["status"] == "rejected"
    assert "GEOMETRY_ERROR" in res["message"] or "above" in res["message"]


def test_12_buy_tp_below_entry():
    res = execution_pipeline.submit_order(
        signal_id=f"BUY_TP_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.1, requested_entry=1.0500, stop_loss=1.0450, take_profit=1.0400
    )
    assert res["status"] == "rejected"
    assert "GEOMETRY_ERROR" in res["message"] or "above" in res["message"]


def test_13_sell_tp_above_entry():
    res = execution_pipeline.submit_order(
        signal_id=f"SELL_TP_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="SELL", volume=0.1, requested_entry=1.0500, stop_loss=1.0550, take_profit=1.0600
    )
    assert res["status"] == "rejected"
    assert "GEOMETRY_ERROR" in res["message"] or "below" in res["message"]


def test_14_invalid_quantity():
    res = execution_pipeline.submit_order(
        signal_id=f"INV_QTY_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=-0.5, requested_entry=1.0500, stop_loss=1.0450
    )
    assert res["status"] == "rejected"
    assert "INVALID" in res["message"] or "Volume" in res["message"]


def test_15_max_daily_loss(monkeypatch):
    database.set_setting("MAX_DAILY_LOSS_PCT", "3.0")
    monkeypatch.setattr(database, "get_account_balances", lambda: {
        "PAPER": {
            "balance": 10000.0,
            "equity": 9500.0,
            "floating_pnl": -400.0,
            "realized_daily_pnl": 0.0
        }
    })
    res = execution_pipeline.submit_order(
        signal_id=f"LOSS_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.01, requested_entry=1.0500, stop_loss=1.0480, mode="PAPER"
    )
    assert res["status"] == "rejected"
    assert "DAILY_LOSS_BREACH" in res["message"]


def test_16_max_symbol_exposure():
    database.set_setting("MAX_SYMBOL_EXPOSURE", "2")
    # Insert 2 existing positions for EURUSD
    conn = database.get_connection()
    cur = conn.cursor()
    now_iso = "2026-08-31T00:00:00"
    for i in range(2):
        if database.is_postgres():
            cur.execute("""
                INSERT INTO open_positions (position_id, account_id, symbol, direction, volume, entry_price, current_price, sl, tp, floating_pnl, swap, open_time, updated_at)
                VALUES (%s, 'PAPER', 'EURUSD', 'BUY', 0.01, 1.0500, 1.0500, 1.0480, 1.0600, 0.0, 0.0, %s, %s)
            """, (f"pos_test_{i}", now_iso, now_iso))
        else:
            cur.execute("""
                INSERT INTO open_positions (position_id, account_id, symbol, direction, volume, entry_price, current_price, sl, tp, floating_pnl, swap, open_time, updated_at)
                VALUES (?, 'PAPER', 'EURUSD', 'BUY', 0.01, 1.0500, 1.0500, 1.0480, 1.0600, 0.0, 0.0, ?, ?)
            """, (f"pos_test_{i}", now_iso, now_iso))
    conn.commit()
    conn.close()

    # 3rd position must be rejected
    res = execution_pipeline.submit_order(
        signal_id=f"MAX_POS_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.01, requested_entry=1.0500, stop_loss=1.0480, mode="PAPER"
    )
    assert res["status"] == "rejected"
    assert "SYMBOL_EXPOSURE_LIMIT" in res["message"]


def test_17_emergency_halt():
    database.set_setting("GLOBAL_KILL_SWITCH", "TRUE")
    res = execution_pipeline.submit_order(
        signal_id=f"HALT_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.01, requested_entry=1.0500, stop_loss=1.0480, mode="PAPER"
    )
    assert res["status"] == "rejected"
    assert "EMERGENCY_HALT_ACTIVE" in res["message"]


def test_18_paper_mode_execution():
    res = execution_pipeline.submit_order(
        signal_id=f"PAPER_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.01, requested_entry=1.0500, stop_loss=1.0480, mode="PAPER"
    )
    assert res["status"] == "success"
    assert res["state"] == ExecutionState.FILLED


def test_19_shadow_mode_execution():
    res = execution_pipeline.submit_order(
        signal_id=f"SHADOW_{uuid.uuid4().hex[:8]}", symbol="EURUSD", direction="BUY", volume=0.01, requested_entry=1.0500, stop_loss=1.0480, mode="SHADOW"
    )
    assert res["status"] == "success"
    assert res["state"] == ExecutionState.FILLED
    # Verify open_positions has zero DB pollution
    df = database.get_open_positions()
    assert df.empty or not any(row.get("position_id", "").startswith("SHADOW") for _, row in df.iterrows())


def test_20_rate_limiter(monkeypatch):
    import server
    server._webhook_rate_limit_cache.clear()
    monkeypatch.setenv("WEBHOOK_SECRET", "changeme_in_production!")
    
    status_codes = []
    for _ in range(25):
        resp = client.post("/api/webhook/tradingview", json={
            "secret": "changeme_in_production!", "signal_id": f"SIG_{uuid.uuid4().hex[:8]}", 
            "timestamp": time.time(), "symbol": "EURUSD", "direction": "BUY", "volume": 0.01, "stop_loss": 1.0480, "current_price": 1.0500
        })
        status_codes.append(resp.status_code)
    
    assert status_codes.count(429) == 5
    assert len([c for c in status_codes if c != 429]) == 20
