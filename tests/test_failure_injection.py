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
    monkeypatch.setenv("WEBHOOK_SECRET", "PAPER_TEST_SECRET")
    monkeypatch.setattr(database, "has_signal", lambda x: False)
    monkeypatch.setattr(database, "record_signal", lambda *args: None)
    monkeypatch.setattr(database, "get_setting", lambda k, d: "PAPER" if k == "SYSTEM_STATE" else d)

def test_failure_injection_db_lock(base_mock, monkeypatch):
    # Simulate database lock/unavailability on open positions query
    def mock_get_conn():
        raise Exception("database is locked")
    monkeypatch.setattr(database, "get_connection", mock_get_conn)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    logs = []
    monkeypatch.setattr(database, "log_execution", lambda d: logs.append(d))
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4()}",
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "take_profit": 1.0600
    })
    
    assert resp.status_code == 400
    assert ("DATABASE ERROR" in resp.json()["detail"] or "unavailable" in resp.json()["detail"].lower())
    assert len(logs) == 1
    assert logs[0]["execution_result"] == "REJECTED"
    
def test_failure_injection_broker_timeout(base_mock, monkeypatch):
    # Simulate a broker response taking too long resulting in timeout exception during state fetch
    def mock_get_state(account_type):
        return {"status": "error", "message": "requests.exceptions.Timeout"}
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4()}",
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0400,
        "take_profit": 1.0600
    })
    
    assert resp.status_code == 400
    # The get_account_state catches exceptions and returns {"status": "error", "message": "..."} internally, but the exception was thrown in my mock before that, so it will raise directly, mimicking a crash. Actually, get_account_state catches its own errors. Let me mock it returning the error properly.
    
def test_failure_injection_broker_error_state(base_mock, monkeypatch):
    def mock_get_state(account_type):
        return {"status": "error", "message": "Connection Timeout"}
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4()}",
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0400,
        "take_profit": 1.0600
    })
    
    assert resp.status_code == 400
    assert "BROKER STATE UNAVAILABLE" in resp.json()["detail"]

def test_failure_injection_market_data_stale(base_mock, monkeypatch):
    # In Phase 9, we enforce staleness on timestamp. Let's make the timestamp very old.
    import server
    server._webhook_rate_limit_cache.clear()
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4()}",
        "timestamp": time.time() - 400, # 400s old (stale limit is 300)
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0400,
        "take_profit": 1.0600
    })
    
    assert resp.status_code == 400
    assert "STALE DATA" in resp.json()["detail"]
