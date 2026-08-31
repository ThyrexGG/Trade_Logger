import pytest
from fastapi.testclient import TestClient
from server import app
import time
import uuid
import database
import account_state

client = TestClient(app)

@pytest.fixture
def mock_db_paper(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "PAPER_TEST_SECRET")
    monkeypatch.setattr(database, "has_signal", lambda x: False)
    monkeypatch.setattr(database, "record_signal", lambda *args: None)
    
    def mock_get_state(account_type):
        return {
            "status": "success",
            "balance": 10000.0,
            "equity": 10000.0,
            "realized_pnl": 0.0,
            "floating_pnl": 0.0,
            "open_positions": [],
            "total_open_risk": 0.0
        }
    monkeypatch.setattr(account_state, "get_account_state", mock_get_state)

def test_paper_execution_end_to_end(mock_db_paper, monkeypatch):
    # Set system state to PAPER
    monkeypatch.setattr(database, "get_setting", lambda k, d: "PAPER" if k == "SYSTEM_STATE" else d)
    
    logs = []
    monkeypatch.setattr(database, "log_execution", lambda d: logs.append(d))
    
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
    
    assert resp.status_code == 200
    assert "success" in resp.json()["status"]
    assert "Paper order executed successfully" in resp.json()["message"]
    
    assert len(logs) == 1
    log = logs[0]
    assert log["execution_result"] == "PAPER_FILLED"
    assert "PAPER_" in log["broker_order_id"]
    assert log["signal_to_execution_latency"] > 0
    assert log["validation_result"] == "PASSED"
    assert log["risk_result"] == "APPROVED"

def test_shadow_execution_end_to_end(mock_db_paper, monkeypatch):
    # Set system state to SHADOW
    monkeypatch.setattr(database, "get_setting", lambda k, d: "SHADOW" if k == "SYSTEM_STATE" else d)
    
    logs = []
    monkeypatch.setattr(database, "log_execution", lambda d: logs.append(d))
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": f"SIG_{uuid.uuid4()}",
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "SELL",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0600
    })
    
    assert resp.status_code == 200
    assert "success" in resp.json()["status"]
    assert "Shadow order would be executed" in resp.json()["message"]
    
    assert len(logs) == 1
    log = logs[0]
    assert log["execution_result"] == "WOULD_EXECUTE"
    assert "SHADOW_" in log["broker_order_id"]
    
def test_shadow_execution_rejects(mock_db_paper, monkeypatch):
    # Shadow mode should log WOULD_REJECT if it hits a validation block
    monkeypatch.setattr(database, "get_setting", lambda k, d: "SHADOW" if k == "SYSTEM_STATE" else d)
    
    logs = []
    monkeypatch.setattr(database, "log_execution", lambda d: logs.append(d))
    
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
        "stop_loss": 1.0600 # Invalid SL for BUY
    })
    
    assert resp.status_code == 400
    
    assert len(logs) == 1
    log = logs[0]
    assert log["execution_result"] == "WOULD_REJECT"
    assert "strictly below" in log["reject_reason"]
