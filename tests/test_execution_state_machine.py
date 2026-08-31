"""
Execution State Machine Unit & Integration Test Suite (Phase 12A)
Verifies:
- All 14 execution states
- Valid state transition graph
- Invariant enforcement (InvalidStateTransitionError)
- Database persistence and idempotency
"""

import pytest
import uuid
from unittest.mock import patch
import database
from execution_pipeline import (
    ExecutionState, 
    validate_state_transition, 
    InvalidStateTransitionError, 
    persist_execution_state, 
    transition_state, 
    execute_signal
)

@pytest.fixture(autouse=True)
def setup_db():
    database.init_db()
    # Reset kill switch for testing
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "PAPER")
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "10.0")


def test_valid_state_transitions():
    """Verify that all legal state transitions pass validation."""
    assert validate_state_transition(ExecutionState.RECEIVED, ExecutionState.VALIDATING) is True
    assert validate_state_transition(ExecutionState.VALIDATING, ExecutionState.MARKET_DATA_VALID) is True
    assert validate_state_transition(ExecutionState.MARKET_DATA_VALID, ExecutionState.RISK_CHECKING) is True
    assert validate_state_transition(ExecutionState.RISK_CHECKING, ExecutionState.RISK_APPROVED) is True
    assert validate_state_transition(ExecutionState.RISK_APPROVED, ExecutionState.SUBMITTING) is True
    assert validate_state_transition(ExecutionState.SUBMITTING, ExecutionState.FILLED) is True
    assert validate_state_transition(ExecutionState.SUBMITTING, ExecutionState.UNKNOWN) is True
    assert validate_state_transition(ExecutionState.UNKNOWN, ExecutionState.RECONCILING) is True
    assert validate_state_transition(ExecutionState.RECONCILING, ExecutionState.RECONCILED) is True


def test_invalid_state_transitions():
    """Verify that impossible transitions raise InvalidStateTransitionError."""
    # Cannot jump from RECEIVED directly to FILLED
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ExecutionState.RECEIVED, ExecutionState.FILLED)
        
    # Cannot jump from VALIDATING directly to SUBMITTING
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ExecutionState.VALIDATING, ExecutionState.SUBMITTING)
        
    # Cannot jump from UNKNOWN directly to FILLED without RECONCILING
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ExecutionState.UNKNOWN, ExecutionState.FILLED)

    # Cannot transition out of terminal FILLED or REJECTED states
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ExecutionState.FILLED, ExecutionState.SUBMITTING)
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ExecutionState.REJECTED, ExecutionState.VALIDATING)


def test_execution_state_persistence_and_query():
    """Verify state machine persists properly to database."""
    exec_id = f"test_exec_{uuid.uuid4().hex[:8]}"
    sig_id = f"test_sig_{uuid.uuid4().hex[:8]}"
    
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
        "mode": "PAPER",
        "state": ExecutionState.RECEIVED
    }
    
    persist_execution_state(state_data)
    
    # Transition to VALIDATING
    transition_state(state_data, ExecutionState.VALIDATING)
    
    # Query database
    conn = database.get_connection()
    cursor = conn.cursor()
    query = "SELECT state, symbol, side FROM execution_orders WHERE execution_id = %s" if database.is_postgres() else "SELECT state, symbol, side FROM execution_orders WHERE execution_id = ?"
    cursor.execute(query, (exec_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == ExecutionState.VALIDATING
    assert row[1] == "EURUSD"
    assert row[2] == "BUY"


def test_signal_id_idempotency():
    """Verify that duplicate signal IDs are rejected and blocked."""
    sig_id = f"idempotent_sig_{uuid.uuid4().hex[:8]}"
    
    signal = {
        "signal_id": sig_id,
        "symbol": "USDJPY",
        "side": "BUY",
        "requested_quantity": 0.01,
        "requested_entry": 155.05,
        "stop_loss": 155.00,
        "take_profit": 155.50,
        "mode": "PAPER"
    }
    
    # First execution succeeds
    with patch("market_data.get_market_health", return_value={"status": "HEALTHY"}), \
         patch("market_data.get_latest_price", return_value=155.05), \
         patch("market_data.get_latest_tick", return_value={"bid": 155.04, "ask": 155.05}):
        res1 = execute_signal(signal)
    assert res1["status"] == "success", f"res1 failed: {res1}"
    
    # Duplicate execution attempt must be blocked
    res2 = execute_signal(signal)
    assert res2["status"] == "error"
    assert "DUPLICATE_SIGNAL" in res2["message"]
