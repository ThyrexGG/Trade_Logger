"""
Phase 33 — PostgreSQL / SQLite Database Query Compatibility Test Suite
Validates that all queries across forward signals, provenance, monitoring,
evidence snapshots, and decision audit work seamlessly with dialect adaptation (%s vs ?).
"""

import pytest
import database
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_alert_engine import XAUUSDAlertEngine
from xauusd_forward_evidence_ledger import ForwardEvidenceLedger
from xauusd_research_decision_audit import ResearchDecisionAuditEngine


def test_database_connection_and_placeholder():
    """Validates database connection retrieval and dialect-specific placeholder adaptation."""
    conn = database.get_connection()
    assert conn is not None
    placeholder = database.get_sql_placeholder(conn)
    assert placeholder in ["?", "%s"]
    conn.close()


def test_query_forward_signals_table():
    """Validates that forward signals table can be queried without SQL syntax errors."""
    df_paper = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
    assert df_paper is not None

    df_shadow = XAUUSDForwardJournal.get_forward_trades(mode="SHADOW")
    assert df_shadow is not None


def test_query_alert_events_table():
    """Validates that monitor events / alert center table can be queried cleanly."""
    alerts = XAUUSDAlertEngine.get_events(limit=10)
    assert isinstance(alerts, list)


def test_query_evidence_snapshots_table():
    """Validates that evidence ledger snapshots table can be queried cleanly."""
    snaps = ForwardEvidenceLedger.get_snapshots(limit=10)
    assert isinstance(snaps, list)


def test_query_decision_audit_table():
    """Validates that decision audit history table can be queried cleanly."""
    history = ResearchDecisionAuditEngine.get_audit_history(limit=5)
    assert isinstance(history, list)
