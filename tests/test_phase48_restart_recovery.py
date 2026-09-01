"""
Phase 48 — Tests for Restart Recovery & Database Reconnection Safety
"""

import pytest
import database
from xauusd_forward_lifecycle import (
    ForwardOutcomeLifecycleManager,
    ForwardLifecycleReconciliationAudit,
    init_phase48_database
)


def test_database_init_reentrant():
    # Calling init multiple times must not crash or duplicate schema
    init_phase48_database()
    init_phase48_database()

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='xauusd_forward_lifecycle_events'")
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "xauusd_forward_lifecycle_events"
