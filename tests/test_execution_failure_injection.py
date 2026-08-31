"""
Execution Pipeline & Broker Reconciliation Failure-Injection Test Suite (Phase 12A)
Mechanically verifies:
- Broker timeouts -> UNKNOWN state (Never assume rejection/failure)
- Unknown state reconciliation (Filled vs Not Filled)
- Correlation risk gating (Same direction vs Hedge)
- Daily loss protection with Floating PnL
- Kill switch enforcement
- Broker discrepancy detection (Broker-only, Local-only, Mismatch)
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
import database
import risk_gateway
import reconciliation
import broker_adapter
from execution_pipeline import ExecutionState, execute_signal, persist_execution_state
from broker_adapter import CanonicalOrderResult, CanonicalPosition, CanonicalAccountState


@pytest.fixture(autouse=True)
def setup_db():
    database.init_db()
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "LIVE")
    database.set_setting("MAX_DAILY_LOSS_PCT", "10.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "50.0")
    database.set_setting("MAX_TRADE_RISK_PCT", "25.0")
    database.set_setting("MAX_SYMBOL_EXPOSURE", "100")
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "100.0")
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM open_positions")
    conn.commit()
    conn.close()


def test_broker_timeout_enters_unknown_state():
    """
    CRITICAL RULE:
    When a network timeout occurs during live order transmission,
    the pipeline MUST enter UNKNOWN state, NOT REJECTED and NOT FAILED.
    """
    sig_id = f"timeout_sig_{uuid.uuid4().hex[:8]}"
    signal = {
        "signal_id": sig_id,
        "symbol": "EURUSD",
        "side": "BUY",
        "requested_quantity": 0.01,
        "requested_entry": 1.0850,
        "stop_loss": 1.0840,
        "take_profit": 1.0950,
        "broker": "CAPITAL",
        "mode": "LIVE"
    }

    # Mock broker adapter throwing TimeoutError and prevent automatic sync reconciliation
    with patch.object(broker_adapter.CapitalComAdapter, "submit_order", side_effect=TimeoutError("Socket recv timeout")), \
         patch("market_data.get_market_health", return_value={"status": "HEALTHY"}), \
         patch("market_data.get_latest_price", return_value=1.0850), \
         patch("market_data.get_latest_tick", return_value={"bid": 1.0848, "ask": 1.0850}), \
         patch("account_state.get_account_state", return_value={"balance": 10000.0, "equity": 10000.0, "status": "HEALTHY", "floating_pnl": 0.0, "realized_daily_pnl": 0.0}), \
         patch("reconciliation.reconcile_execution"):
        res = execute_signal(signal)
        
    assert res["status"] == "unknown"
    assert res["state"] == ExecutionState.UNKNOWN
    assert "UNKNOWN" in res["message"]
    
    # Verify persisted in database as UNKNOWN
    conn = database.get_connection()
    cursor = conn.cursor()
    q = "SELECT state, reconciliation_status FROM execution_orders WHERE signal_id = %s" if database.is_postgres() else "SELECT state, reconciliation_status FROM execution_orders WHERE signal_id = ?"
    cursor.execute(q, (sig_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == ExecutionState.UNKNOWN
    assert row[1] == "PENDING_RECONCILIATION"


def test_reconciliation_resolves_unknown_to_filled():
    """
    If an order timed out but the broker DID execute it,
    reconciliation must find the position and transition to RECONCILED / FILLED.
    """
    exec_id = f"exec_rec_fill_{uuid.uuid4().hex[:8]}"
    sig_id = f"sig_rec_fill_{uuid.uuid4().hex[:8]}"
    
    state_data = {
        "execution_id": exec_id,
        "signal_id": sig_id,
        "symbol": "EURUSD",
        "side": "BUY",
        "requested_quantity": 0.1,
        "requested_entry": 1.0850,
        "stop_loss": 1.0800,
        "take_profit": 1.0950,
        "broker": "CAPITAL",
        "mode": "LIVE",
        "state": ExecutionState.UNKNOWN
    }
    persist_execution_state(state_data)
    
    # Mock broker returning matching position
    mock_pos = CanonicalPosition(
        ticket="deal_998877",
        symbol="EURUSD",
        direction="BUY",
        volume=0.1,
        entry_price=1.0850,
        current_price=1.0855,
        sl=1.0800,
        tp=1.0950
    )
    
    with patch("broker_adapter.CapitalComAdapter.get_open_positions", return_value=[mock_pos]):
        recon_res = reconciliation.reconcile_execution(exec_id)
        
    assert recon_res["status"] == "resolved"
    assert recon_res["resolution"] == "FILLED"
    assert recon_res["broker_ticket"] == "deal_998877"
    
    # Verify DB updated
    conn = database.get_connection()
    cursor = conn.cursor()
    q = "SELECT state, broker_order_id, reconciliation_status FROM execution_orders WHERE execution_id = %s" if database.is_postgres() else "SELECT state, broker_order_id, reconciliation_status FROM execution_orders WHERE execution_id = ?"
    cursor.execute(q, (exec_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row[0] == ExecutionState.RECONCILED
    assert row[1] == "deal_998877"
    assert row[2] == "RESOLVED_FILLED"


def test_reconciliation_resolves_unknown_to_not_filled():
    """
    If an order timed out and broker confirms NO position exists,
    reconciliation transitions to RECONCILED / NOT_FILLED without fabricating a fill.
    """
    exec_id = f"exec_rec_nofill_{uuid.uuid4().hex[:8]}"
    sig_id = f"sig_rec_nofill_{uuid.uuid4().hex[:8]}"
    
    state_data = {
        "execution_id": exec_id,
        "signal_id": sig_id,
        "symbol": "USDJPY",
        "side": "SELL",
        "requested_quantity": 0.2,
        "requested_entry": 155.00,
        "broker": "MT5",
        "mode": "LIVE",
        "state": ExecutionState.UNKNOWN
    }
    persist_execution_state(state_data)
    
    # Mock broker returning empty positions
    with patch("broker_adapter.MT5Adapter.get_open_positions", return_value=[]):
        recon_res = reconciliation.reconcile_execution(exec_id)
        
    assert recon_res["status"] == "resolved"
    assert recon_res["resolution"] == "NOT_FILLED"
    
    conn = database.get_connection()
    cursor = conn.cursor()
    q = "SELECT state, reconciliation_status FROM execution_orders WHERE execution_id = %s" if database.is_postgres() else "SELECT state, reconciliation_status FROM execution_orders WHERE execution_id = ?"
    cursor.execute(q, (exec_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row[0] == ExecutionState.RECONCILED
    assert row[1] == "RESOLVED_NOT_FILLED"


def test_kill_switch_blocks_execution():
    """Emergency kill switch must immediately reject new orders across all paths."""
    database.set_setting("GLOBAL_KILL_SWITCH", "TRUE")
    
    sig_id = f"halt_sig_{uuid.uuid4().hex[:8]}"
    signal = {
        "signal_id": sig_id,
        "symbol": "EURUSD",
        "side": "BUY",
        "requested_quantity": 0.1,
        "requested_entry": 1.0850,
        "stop_loss": 1.0800,
        "mode": "LIVE"
    }
    
    res = execute_signal(signal)
    assert res["status"] == "rejected"
    assert res["state"] == ExecutionState.REJECTED
    assert "EMERGENCY_HALT_ACTIVE" in res["message"]


def test_directional_correlation_risk_rejection():
    """
    Directional correlation risk:
    Opening LONG EURUSD when LONG GBPUSD is already open (>0.80 correlation)
    must be rejected to prevent excessive USD risk accumulation.
    """
    # Insert open position on GBPUSD
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM open_positions")
    now_iso = "2026-08-31T00:00:00"
    if database.is_postgres():
        cursor.execute("""
            INSERT INTO open_positions (position_id, account_id, symbol, direction, volume, entry_price, current_price, sl, tp, floating_pnl, swap, open_time, updated_at)
            VALUES ('pos_gbp_1', 'CAPITAL', 'GBPUSD', 'BUY', 0.01, 1.3000, 1.3005, 1.2990, 1.3050, 5.0, 0.0, %s, %s)
        """, (now_iso, now_iso))
    else:
        cursor.execute("""
            INSERT INTO open_positions (position_id, account_id, symbol, direction, volume, entry_price, current_price, sl, tp, floating_pnl, swap, open_time, updated_at)
            VALUES ('pos_gbp_1', 'CAPITAL', 'GBPUSD', 'BUY', 0.01, 1.3000, 1.3005, 1.2990, 1.3050, 5.0, 0.0, ?, ?)
        """, (now_iso, now_iso))
    conn.commit()
    conn.close()
    
    # Propose new BUY on EURUSD (correlation ~0.84)
    signal = {
        "symbol": "EURUSD",
        "side": "BUY",
        "requested_quantity": 0.01,
        "requested_entry": 1.0850,
        "stop_loss": 1.0840,
        "broker": "CAPITAL",
        "mode": "PAPER"
    }
    
    with patch("market_data.get_market_health", return_value={"status": "HEALTHY"}):
        risk_res = risk_gateway.evaluate_trade_risk(signal)
    assert risk_res["approved"] is False
    assert any("CORRELATION_RISK" in r for r in risk_res["reasons"])


def test_daily_loss_protection_with_floating_pnl():
    """
    Daily loss limit must account for broker-reported floating PnL.
    If realized = -$100 and floating = -$250 (total -$350), and limit is -$300 (3% of $10,000),
    the trade must be rejected.
    """
    database.set_setting("MAX_DAILY_LOSS_PCT", "3.0")
    mock_account = {
        "status": "success",
        "balance": 10000.0,
        "equity": 9650.0,
        "floating_pnl": -250.0,
        "realized_daily_pnl": -100.0
    }
    
    signal = {
        "symbol": "USDJPY",
        "side": "BUY",
        "requested_quantity": 0.01,
        "requested_entry": 155.00,
        "stop_loss": 154.90,
        "broker": "CAPITAL",
        "mode": "LIVE"
    }
    
    with patch("risk_gateway.get_account_state", return_value=mock_account), \
         patch("market_data.get_market_health", return_value={"status": "HEALTHY"}):
        risk_res = risk_gateway.evaluate_trade_risk(signal)
        
    assert risk_res["approved"] is False
    assert any("DAILY_LOSS_BREACH" in r for r in risk_res["reasons"])


def test_reconciliation_detects_broker_only_orphan_positions():
    """Reconciliation must detect positions that exist on broker but not in local DB."""
    # Local DB has 0 positions
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM open_positions")
    conn.commit()
    conn.close()
    
    # Broker has 1 orphan position
    mock_orphan = CanonicalPosition(
        ticket="orphan_112233",
        symbol="XAUUSD",
        direction="BUY",
        volume=0.5,
        entry_price=2500.0,
        current_price=2505.0,
        floating_pnl=250.0
    )
    
    with patch("broker_adapter.MT5Adapter.get_open_positions", return_value=[mock_orphan]):
        recon_res = reconciliation.reconcile_open_positions("MT5")
        
    assert recon_res["status"].upper() == "MISMATCH"
    assert len(recon_res["broker_only"]) == 1
    assert recon_res["broker_only"][0]["ticket"] == "orphan_112233"
    
    # Startup reconciliation must block automation when orphan position is detected
    with patch("broker_adapter.MT5Adapter.get_open_positions", return_value=[mock_orphan]):
        startup_res = reconciliation.startup_reconciliation()
        
    assert startup_res["automation_allowed"] is False
    assert startup_res["status"] == "BLOCKED"
