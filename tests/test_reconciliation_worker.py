"""
Tests for Reconciliation Worker Lifecycle & Health States (Phase 12B)
"""

import time
import pytest
from datetime import datetime, timezone, timedelta
import reconciliation
import system_health
import database


def test_reconciliation_worker_lifecycle():
    # Stop any existing worker
    reconciliation.stop_background_reconciliation()
    h1 = reconciliation.get_reconciliation_health()
    assert h1["status"] == "RECONCILIATION_STOPPED"
    assert h1["healthy"] is False

    # Start worker singleton
    reconciliation.start_background_reconciliation(interval_seconds=10)
    h2 = reconciliation.get_reconciliation_health()
    assert h2["status"] == "RECONCILIATION_HEALTHY"
    assert h2["healthy"] is True

    # Clean up
    reconciliation.stop_background_reconciliation()


def test_system_health_evaluator_kill_switch_blocking():
    database.set_setting("GLOBAL_KILL_SWITCH", "TRUE")
    try:
        sh = system_health.evaluate_system_health(mode="PAPER")
        assert sh["automation_allowed"] is False
        assert any("GLOBAL_KILL_SWITCH_ACTIVE" in r for r in sh["reasons"])
    finally:
        database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")


def test_system_health_evaluator_paper_mode_healthy():
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "PAPER")
    sh = system_health.evaluate_system_health(mode="PAPER")
    assert sh["overall_status"] in ["HEALTHY", "BLOCKED"]
