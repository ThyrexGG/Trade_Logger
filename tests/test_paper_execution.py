import pytest
from fastapi.testclient import TestClient
from server import app
import time
import uuid
import database
import account_state
from execution_pipeline import ExecutionState

client = TestClient(app)

@pytest.fixture
def mock_db_paper(monkeypatch):
    database.init_db()
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "100.0")
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("MAX_TRADE_RISK_PCT", "10.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "50.0")
    database.set_setting("MAX_DAILY_LOSS_PCT", "10.0")
    database.set_setting("MAX_SYMBOL_EXPOSURE", "10")
    
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM open_positions")
    cur.execute("DELETE FROM execution_orders")
    conn.commit()
    conn.close()
    
    monkeypatch.setenv("WEBHOOK_SECRET", "PAPER_TEST_SECRET")
    monkeypatch.setattr(database, "has_signal", lambda x: False)
    monkeypatch.setattr(database, "record_signal", lambda *args: None)
    import market_data
    monkeypatch.setattr(market_data, "get_market_health", lambda sym, tf: {"status": "HEALTHY"})
    monkeypatch.setattr(market_data, "get_latest_tick", lambda sym: {"bid": 1.0500, "ask": 1.0502})
    monkeypatch.setattr(market_data, "get_latest_price", lambda sym: 1.0500)
    
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
    monkeypatch.setattr(database, "get_setting", lambda k, d: "PAPER" if k == "SYSTEM_STATE" else d)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    sig_id = f"SIG_PAPER_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": sig_id,
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
    
    # Check database state
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT state, mode FROM execution_orders WHERE signal_id = ?", (sig_id,))
    row = cur.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == ExecutionState.FILLED
    assert row[1] == "PAPER"

def test_shadow_execution_end_to_end(mock_db_paper, monkeypatch):
    monkeypatch.setattr(database, "get_setting", lambda k, d: "SHADOW" if k == "SYSTEM_STATE" else d)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    sig_id = f"SIG_SHADOW_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": sig_id,
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "SELL",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0600
    })
    
    assert resp.status_code == 200
    assert "success" in resp.json()["status"]
    
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT state, mode FROM execution_orders WHERE signal_id = ?", (sig_id,))
    row = cur.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == ExecutionState.FILLED
    assert row[1] == "SHADOW"
    
def test_shadow_execution_rejects(mock_db_paper, monkeypatch):
    monkeypatch.setattr(database, "get_setting", lambda k, d: "SHADOW" if k == "SYSTEM_STATE" else d)
    
    import server
    server._webhook_rate_limit_cache.clear()
    
    sig_id = f"SIG_SHADOW_REJ_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/webhook/tradingview", json={
        "secret": "PAPER_TEST_SECRET",
        "signal_id": sig_id,
        "timestamp": time.time(),
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.1,
        "current_price": 1.0500,
        "stop_loss": 1.0600 # Invalid SL for BUY
    })
    
    assert resp.status_code == 400
    
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT state, reject_reason FROM execution_orders WHERE signal_id = ?", (sig_id,))
    row = cur.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == ExecutionState.REJECTED
    assert "below" in row[1] or "GEOMETRY_ERROR" in row[1]
