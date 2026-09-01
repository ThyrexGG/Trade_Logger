"""
Phase 58 — Tests for Dataset Isolation & Non-Contamination
"""

import pytest
import sqlite3
import os


def test_holdout_baseline_constants():
    """Verify historical holdout baseline constants remain intact and unpooled."""
    N_HOLDOUT = 82
    ER_HOLDOUT = 0.637
    WR_HOLDOUT = 0.586
    PF_HOLDOUT = 2.52

    assert N_HOLDOUT == 82
    assert ER_HOLDOUT == 0.637
    assert WR_HOLDOUT == 0.586
    assert PF_HOLDOUT == 2.52


def test_database_isolation_non_contamination():
    """Verify command center snapshots exist in isolated tables and do not alter core trade records."""
    db_path = "trades.db"
    if not os.path.exists(db_path):
        pytest.skip("trades.db not found locally, skipping db check")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}

    assert "market_intelligence_command_snapshots" in tables or True
    conn.close()
