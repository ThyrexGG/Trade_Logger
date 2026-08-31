"""
Phase 31 — Restart Recovery, Replay Protection & Live Safety Invariants Test Suite
Validates application restart recovery, duplicate signal replay suppression,
hard-coded live trading safety barrier, and Strategy Contract SHA-256 immutability.
"""

import os
import hashlib
import pytest
from datetime import datetime, timezone
import database
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_research_governance import LiveTradingSafetyBarrier, LiveAutomationBlockedException
from xauusd_operational_monitor import FROZEN_CONTRACT_HASH


def test_strategy_contract_hash_immutability():
    """Validates that PHASE_21_XAUUSD_STRATEGY_CONTRACT.md matches exact frozen SHA-256 hash."""
    contract_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)

    with open(contract_path, "rb") as f:
        computed_hash = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()

    assert computed_hash == FROZEN_CONTRACT_HASH
    
    guard = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert guard["parameters_verified"] is True
    assert guard["integrity_status"] == "FROZEN & LOCKED"


def test_live_trading_safety_barrier_blocks_transmission():
    """Validates that live trading safety barrier permanently blocks broker transmission."""
    status = LiveTradingSafetyBarrier.enforce_live_barrier("PAPER")
    assert status["live_automation_blocked"] is True
    assert status["status"] == "SAFETY LOCK ACTIVE"

    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_idempotent_signal_replay_protection():
    """Validates that duplicate signal logging is safely handled (idempotent / upsert)."""
    XAUUSDForwardJournal.init_forward_table()
    test_sig_id = "SIG_REPLAY_TEST_PHASE31_001"
    now_iso = datetime.now(timezone.utc).isoformat()

    sig_data = {
        "signal_id": test_sig_id,
        "timestamp": now_iso,
        "symbol": "XAUUSD",
        "bias_1d": "BULLISH",
        "target_4h": "BSL_SWING_HIGH",
        "sweep_15m": "CONFIRMED_SWEEP",
        "mss_15m": "BULLISH_MSS",
        "conf_5m": "BULLISH_FVG_5M",
        "entry_type_1m": "1M_FVG_LIMIT",
        "requested_entry": 2415.00,
        "stop_loss": 2410.00,
        "take_profit": 2430.00,
        "planned_rr": 3.00,
        "execution_mode": "PAPER",
        "status": "FILLED",
        "realized_r": 1.5,
    }

    # Log once
    res1 = XAUUSDForwardJournal.log_forward_signal(sig_data)
    assert res1 == test_sig_id

    # Log again (duplicate replay simulation)
    res2 = XAUUSDForwardJournal.log_forward_signal(sig_data)
    assert res2 == test_sig_id

    # Verify query returns single record with this ID, not duplicate rows
    df = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
    matches = df[df["signal_id"] == test_sig_id]
    assert len(matches) == 1
    assert float(matches.iloc[0]["realized_r"]) == 1.5


def test_database_connection_and_reconnect_resilience():
    """Validates that get_connection safely reconnects and handles queries without crashing."""
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1")
    res = cur.fetchone()
    assert res[0] == 1
    conn.close()

    # Reconnect
    conn2 = database.get_connection()
    cur2 = conn2.cursor()
    cur2.execute("SELECT 1")
    res2 = cur2.fetchone()
    assert res2[0] == 1
    conn2.close()
