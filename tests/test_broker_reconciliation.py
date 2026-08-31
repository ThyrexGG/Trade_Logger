"""
Tests for Broker Reconciliation Layer (Phase 12B)
"""

import pytest
import pandas as pd
from reconciliation import reconcile_open_positions, perform_system_recovery_check
import broker_adapter
from broker_adapter import CanonicalPosition, CanonicalBrokerStatus, BrokerAdapter
import database


class MockReconAdapter(BrokerAdapter):
    def __init__(self, positions):
        self._positions = positions
        
    def health_check(self):
        return CanonicalBrokerStatus(broker="MT5", connected=True)
        
    def get_account_state(self):
        return None
        
    def get_open_positions(self):
        return self._positions
        
    def submit_order(self, *args, **kwargs):
        pass
        
    def close_position(self, *args, **kwargs):
        pass
        
    def modify_position(self, *args, **kwargs):
        pass


@pytest.fixture
def mock_db_reconciliation(monkeypatch):
    monkeypatch.setattr(database, "get_open_positions", lambda: pd.DataFrame([
        {"position_id": "MT5_101", "symbol": "EURUSD", "direction": "BUY", "volume": 0.1, "entry_price": 1.0, "sl": 0.9, "tp": 1.1, "floating_pnl": 0.0},
        {"position_id": "MT5_102", "symbol": "GBPUSD", "direction": "SELL", "volume": 0.2, "entry_price": 1.2, "sl": 1.3, "tp": 1.1, "floating_pnl": 0.0},
    ]))


def test_reconciliation_perfect_match(mock_db_reconciliation, monkeypatch):
    mock_positions = [
        CanonicalPosition(ticket="101", symbol="EURUSD", direction="BUY", volume=0.1, entry_price=1.0, current_price=1.0, sl=0.9, tp=1.1),
        CanonicalPosition(ticket="102", symbol="GBPUSD", direction="SELL", volume=0.2, entry_price=1.2, current_price=1.2, sl=1.3, tp=1.1),
    ]
    monkeypatch.setattr(broker_adapter, "get_broker_adapter", lambda b: MockReconAdapter(mock_positions))
    
    res = reconcile_open_positions("MT5")
    assert res["status"] == "matched"
    assert len(res["matched"]) == 2
    assert len(res["mismatched"]) == 0
    assert len(res["broker_only"]) == 0
    assert len(res["local_only"]) == 0


def test_reconciliation_local_only(mock_db_reconciliation, monkeypatch):
    # Broker only has 101. 102 was closed on broker
    mock_positions = [
        CanonicalPosition(ticket="101", symbol="EURUSD", direction="BUY", volume=0.1, entry_price=1.0, current_price=1.0, sl=0.9, tp=1.1),
    ]
    monkeypatch.setattr(broker_adapter, "get_broker_adapter", lambda b: MockReconAdapter(mock_positions))
    
    res = reconcile_open_positions("MT5")
    assert res["status"] == "mismatch"
    assert len(res["local_only"]) == 1
    assert res["local_only"][0]["ticket"] == "102"


def test_reconciliation_broker_only(mock_db_reconciliation, monkeypatch):
    # Broker has a new trade 103 not in DB
    mock_positions = [
        CanonicalPosition(ticket="101", symbol="EURUSD", direction="BUY", volume=0.1, entry_price=1.0, current_price=1.0, sl=0.9, tp=1.1),
        CanonicalPosition(ticket="102", symbol="GBPUSD", direction="SELL", volume=0.2, entry_price=1.2, current_price=1.2, sl=1.3, tp=1.1),
        CanonicalPosition(ticket="103", symbol="XAUUSD", direction="BUY", volume=0.5, entry_price=2000.0, current_price=2000.0, sl=1900.0, tp=2100.0),
    ]
    monkeypatch.setattr(broker_adapter, "get_broker_adapter", lambda b: MockReconAdapter(mock_positions))
    
    res = reconcile_open_positions("MT5")
    assert res["status"] == "mismatch"
    assert len(res["broker_only"]) == 1
    assert res["broker_only"][0]["ticket"] == "103"


def test_reconciliation_mismatched_sl(mock_db_reconciliation, monkeypatch):
    # SL was changed manually on broker for 101
    mock_positions = [
        CanonicalPosition(ticket="101", symbol="EURUSD", direction="BUY", volume=0.1, entry_price=1.0, current_price=1.0, sl=0.95, tp=1.1), # 0.9 in DB
        CanonicalPosition(ticket="102", symbol="GBPUSD", direction="SELL", volume=0.2, entry_price=1.2, current_price=1.2, sl=1.3, tp=1.1),
    ]
    monkeypatch.setattr(broker_adapter, "get_broker_adapter", lambda b: MockReconAdapter(mock_positions))
    
    res = reconcile_open_positions("MT5")
    assert res["status"] == "mismatch"
    assert len(res["mismatched"]) == 1
    assert any("SL mismatch" in issue for issue in res["mismatched"][0]["issues"])


def test_system_recovery_kill_switch_active(monkeypatch):
    monkeypatch.setattr(database, "get_setting", lambda k, d: "EMERGENCY HALT" if k == "SYSTEM_STATE" else d)
    res = perform_system_recovery_check()
    assert res["status"] == "halted"
