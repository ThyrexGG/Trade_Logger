import pytest
import time
import uuid
import execution_pipeline
import order_execution
from fastapi.testclient import TestClient
from server import app
import os
import database
import pandas as pd
import account_state

client = TestClient(app)

@pytest.fixture
def mock_db(monkeypatch):
    """Mocks database checks to avoid failing tests due to no real DB connection."""
    def mock_get_account_state(account_type):
        return {
            "status": "success",
            "balance": 10000.0,
            "equity": 10000.0,
            "realized_pnl": 0.0,
            "floating_pnl": 0.0,
            "open_positions": [],
            "total_open_risk": 0.0
        }
    monkeypatch.setattr(account_state, "get_account_state", mock_get_account_state)
    def mock_get_setting(key, default):
        if key == "SYSTEM_STATE":
            return "PAPER"
        return default
    monkeypatch.setattr(database, "get_setting", mock_get_setting)
    
    def mock_read_sql(*args, **kwargs):
        # Mock empty dataframes for open positions and daily loss
        if "COUNT(*)" in args[0]:
            return pd.DataFrame([{"cnt": 0}])
        elif "SUM" in args[0] or "net_profit" in args[0]:
            return pd.DataFrame([{"net_profit": 0.0}])
        return pd.DataFrame()
    monkeypatch.setattr(database.pd, "read_sql_query", mock_read_sql)
    
    monkeypatch.setattr(database, "log_execution", lambda x: None)
    monkeypatch.setattr(database, "record_signal", lambda *args: None)
    monkeypatch.setattr(database, "has_signal", lambda x: False)
    
    monkeypatch.setattr(order_execution, "execute_mt5_trade", lambda **kwargs: {"status": "success", "message": "Mocked", "order_id": "MOCK_123", "execution_price": 1.0})
    monkeypatch.setattr(order_execution, "execute_capital_trade", lambda **kwargs: {"status": "success", "message": "Mocked", "order_id": "MOCK_456", "execution_price": 1.0})

def test_1_invalid_webhook_secret(mock_db, monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "SUPER_SECRET")
    response = client.post("/api/webhook/tradingview", json={
        "secret": "WRONG_SECRET", "signal_id": "SIG1", "timestamp": time.time(),
        "symbol": "EURUSD", "direction": "BUY", "volume": 0.1
    })
    assert response.status_code == 401

def test_2_missing_secret(mock_db):
    response = client.post("/api/webhook/tradingview", json={
        "signal_id": "SIG1", "timestamp": time.time(), "symbol": "EURUSD", "direction": "BUY", "volume": 0.1
    })
    assert response.status_code == 422 # Pydantic validation error

def test_3_expired_timestamp(mock_db):
    res = execution_pipeline.submit_order(
        signal_id=f"SIG_{uuid.uuid4()}", symbol="EURUSD", direction="BUY", volume=0.1,
        timestamp=time.time() - 600, current_price=1.0500
    )
    assert res["status"] == "error" and "STALE" in res["message"]

def test_4_future_timestamp(mock_db):
    res = execution_pipeline.submit_order(
        signal_id=f"SIG_{uuid.uuid4()}", symbol="EURUSD", direction="BUY", volume=0.1,
        timestamp=time.time() + 10, current_price=1.0500
    )
    assert res["status"] == "error" and "FUTURE" in res["message"]

def test_5_duplicate_signal(mock_db, monkeypatch):
    monkeypatch.setattr(database, "has_signal", lambda x: True)
    res = execution_pipeline.submit_order(
        signal_id="SIG123", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.0500
    )
    assert res["status"] == "error" and "DUPLICATE SIGNAL" in res["message"]

def test_6_malformed_json():
    response = client.post("/api/webhook/tradingview", content="NOT JSON")
    assert response.status_code == 422

def test_7_missing_required_fields():
    response = client.post("/api/webhook/tradingview", json={"secret": "TV_HOOK_123!"}) # Missing signal_id, symbol, etc
    assert response.status_code == 422

def test_8_invalid_direction(mock_db):
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="HOLD", volume=0.1, timestamp=time.time(), current_price=1.0
    )
    assert res["status"] == "error" and "INVALID RISK PARAMS" in res["message"]

def test_9_unknown_symbol(mock_db):
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="DOGEUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.0
    )
    assert res["status"] == "error" and "WHITELISTED" in res["message"]

def test_10_buy_sl_above_entry(mock_db):
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05, stop_loss=1.06
    )
    assert res["status"] == "error" and "strictly below" in res["message"]

def test_11_sell_sl_below_entry(mock_db):
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="SELL", volume=0.1, timestamp=time.time(), current_price=1.05, stop_loss=1.04
    )
    assert res["status"] == "error" and "strictly above" in res["message"]

def test_12_buy_tp_below_entry(mock_db):
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05, take_profit=1.04
    )
    assert res["status"] == "error" and "strictly above" in res["message"]

def test_13_sell_tp_above_entry(mock_db):
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="SELL", volume=0.1, timestamp=time.time(), current_price=1.05, take_profit=1.06
    )
    assert res["status"] == "error" and "strictly below" in res["message"]

def test_14_invalid_quantity(mock_db):
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=-0.5, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "Volume must be greater than 0" in res["message"]

def test_15_max_daily_loss(mock_db, monkeypatch):
    def mock_get_state_loss(account_type):
        return {
            "status": "success",
            "balance": 10000.0,
            "equity": 10000.0,
            "realized_pnl": -501.0,
            "floating_pnl": 0.0,
            "open_positions": [],
            "total_open_risk": 0.0
        }
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state_loss)
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "MAX DAILY LOSS" in res["message"]

def test_16_max_open_positions(mock_db, monkeypatch):
    def mock_get_state_pos(account_type):
        return {
            "status": "success",
            "balance": 10000.0,
            "equity": 10000.0,
            "realized_pnl": 0.0,
            "floating_pnl": 0.0,
            "open_positions": [{"ticket": str(i), "symbol": f"SYM{i}", "direction": "BUY", "volume": 0.1, "entry": 1.0, "sl": 0.9, "tp": 1.1} for i in range(5)],
            "total_open_risk": 0.0
        }
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state_pos)
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "MAX OPEN POSITIONS" in res["message"]

def test_17_duplicate_existing_position(mock_db, monkeypatch):
    def mock_get_state_dup(account_type):
        return {
            "status": "success",
            "balance": 10000.0,
            "equity": 10000.0,
            "realized_pnl": 0.0,
            "floating_pnl": 0.0,
            "open_positions": [{"ticket": "1", "symbol": "EURUSD", "direction": "BUY", "volume": 0.1, "entry": 1.0, "sl": 0.9, "tp": 1.1}],
            "total_open_risk": 0.0
        }
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state_dup)
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "DUPLICATE POSITION" in res["message"]

def test_18_emergency_halt(mock_db, monkeypatch):
    def mock_get_setting_halt(key, default):
        if key == "SYSTEM_STATE": return "EMERGENCY HALT"
        return default
    monkeypatch.setattr(database, "get_setting", mock_get_setting_halt)
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "EMERGENCY HALT" in res["message"]

def test_19_paper_mode(mock_db):
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05, account_type="MT5"
    )
    assert res["status"] == "success" and "PAPER_" in res["ticket"]

def test_20_successful_live_execution(mock_db, monkeypatch):
    def mock_get_setting_live(key, default):
        if key == "SYSTEM_STATE": return "LIVE"
        return default
    monkeypatch.setattr(database, "get_setting", mock_get_setting_live)
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05, account_type="MT5"
    )
    assert res["status"] == "success" and res["ticket"] == "MOCK_123"

def test_21_broker_rejection(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_setting", lambda k, d: "LIVE" if k == "SYSTEM_STATE" else d)
    monkeypatch.setattr(order_execution, "execute_mt5_trade", lambda **kwargs: {"status": "error", "message": "Insufficient margin"})
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=100.0, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "margin" in res["message"]

def test_22_broker_timeout_unknown_state(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_setting", lambda k, d: "LIVE" if k == "SYSTEM_STATE" else d)
    monkeypatch.setattr(order_execution, "execute_mt5_trade", lambda **kwargs: {"status": "error", "message": "Connection timeout"})
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "DO NOT RETRY" in res["message"]

def test_23_database_fail_closed_idempotency(mock_db, monkeypatch):
    def mock_has_signal_raise(x): raise Exception("DB Down")
    monkeypatch.setattr(database, "has_signal", mock_has_signal_raise)
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "Fail closed" in res["message"]

def test_24_database_fail_closed_risk(mock_db, monkeypatch):
    def mock_get_state_raise(account_type):
        return {"status": "error", "message": "DB Down"}
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state_raise)
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "Fail closed" in res["message"]

def test_25_database_fail_closed_open_pos(mock_db, monkeypatch):
    def mock_get_state_raise_pos(account_type):
        return {"status": "error", "message": "DB Down"}
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state_raise_pos)
    res = execution_pipeline.submit_order(
        signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.05
    )
    assert res["status"] == "error" and "Fail closed" in res["message"]

def test_26_rate_limiter(mock_db, monkeypatch):
    import server
    server._webhook_rate_limit_cache.clear()
    
    monkeypatch.setenv("WEBHOOK_SECRET", "changeme_in_production!")
    # Send 25 requests. The 21st should fail with 429
    status_codes = []
    for _ in range(25):
        resp = client.post("/api/webhook/tradingview", json={
            "secret": "changeme_in_production!", "signal_id": f"SIG_{uuid.uuid4()}", 
            "timestamp": time.time(), "symbol": "EURUSD", "direction": "BUY", "volume": 0.1
        })
        status_codes.append(resp.status_code)
    
    assert status_codes.count(200) == 20
    assert status_codes.count(429) == 5

def test_27_live_paper_parity(mock_db, monkeypatch):
    # Both modes should get exact same pre-execution handling
    monkeypatch.setattr(database, "get_setting", lambda k, d: "LIVE" if k == "SYSTEM_STATE" else d)
    res_live = execution_pipeline.submit_order(signal_id="L1", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.0)
    
    monkeypatch.setattr(database, "get_setting", lambda k, d: "PAPER" if k == "SYSTEM_STATE" else d)
    res_paper = execution_pipeline.submit_order(signal_id="P1", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.0)
    
    assert res_live["status"] == "success" and res_paper["status"] == "success"

def test_28_execution_state_machine_logging(mock_db, monkeypatch):
    logs = []
    def mock_log(d): logs.append(d.copy())
    monkeypatch.setattr(database, "log_execution", mock_log)
    
    res = execution_pipeline.submit_order(signal_id="SIG", symbol="EURUSD", direction="BUY", volume=0.1, timestamp=time.time(), current_price=1.0)
    
    assert len(logs) > 0
    assert logs[0]["execution_result"] == "PAPER_FILLED"
    assert logs[0]["risk_result"] == "APPROVED"
    assert logs[0]["validation_result"] == "PASSED"
