import pytest
from fastapi.testclient import TestClient
from server import app
import time
import uuid
import database
import account_state

client = TestClient(app)

@pytest.fixture
def base_mock(monkeypatch):
    database.init_db()
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "100.0")
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    monkeypatch.setenv("WEBHOOK_SECRET", "PAPER_TEST_SECRET")
    monkeypatch.setattr(database, "has_signal", lambda x: False)
    monkeypatch.setattr(database, "record_signal", lambda *args: None)
    monkeypatch.setattr(database, "get_setting", lambda k, d: "PAPER" if k == "SYSTEM_STATE" else d)
    import market_data
    monkeypatch.setattr(market_data, "get_market_health", lambda sym, tf: {"status": "HEALTHY"})
    monkeypatch.setattr(market_data, "get_latest_tick", lambda sym: {"bid": 1.0500, "ask": 1.0502})
    monkeypatch.setattr(market_data, "get_latest_price", lambda sym: 1.0500)

def test_failure_injection_db_lock(base_mock, monkeypatch):
    # Simulate database lock/unavailability on open positions query
    def mock_get_conn():
        raise Exception("database is locked")
    monkeypatch.setattr(database, "get_connection", mock_get_conn)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4().hex[:8]}",
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0400,
        "take_profit": 1.0600
    })
    
    assert resp.status_code == 400
    assert "locked" in resp.json()["detail"].lower() or "database" in resp.json()["detail"].lower()
    
def test_failure_injection_broker_timeout(base_mock, monkeypatch):
    monkeypatch.setattr(database, "get_setting", lambda k, d: "LIVE" if k == "SYSTEM_STATE" else d)
    def mock_get_state(account_type):
        return {"status": "error", "message": "requests.exceptions.Timeout"}
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4().hex[:8]}",
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0400,
        "take_profit": 1.0600
    })
    
    assert resp.status_code == 400
    assert "UNAVAILABLE_ACCOUNT_STATE" in resp.json()["detail"] or "Timeout" in resp.json()["detail"]

def test_failure_injection_broker_error_state(base_mock, monkeypatch):
    monkeypatch.setattr(database, "get_setting", lambda k, d: "LIVE" if k == "SYSTEM_STATE" else d)
    def mock_get_state(account_type):
        return {"status": "error", "message": "Connection Timeout"}
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4().hex[:8]}",
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0400,
        "take_profit": 1.0600
    })
    
    assert resp.status_code == 400
    assert "UNAVAILABLE_ACCOUNT_STATE" in resp.json()["detail"] or "Timeout" in resp.json()["detail"]

def test_failure_injection_market_data_stale(base_mock, monkeypatch):
    import server
    server._webhook_rate_limit_cache.clear()
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4().hex[:8]}",
        "timestamp": time.time() - 400, # 400s old (stale limit is 300)
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0400,
        "take_profit": 1.0600
    })
    
    assert resp.status_code == 400
    assert "STALE" in resp.json()["detail"]
