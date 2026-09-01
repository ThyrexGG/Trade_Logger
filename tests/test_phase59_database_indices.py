"""
TradeLogger Phase 59 — Database Indices & Query Optimization Tests
==================================================================
Validates presence and correctness of composite timestamp indices
on all snapshot tables in SQLite.
"""

import sqlite3
import pytest
import database
from market_intelligence_command_center import _ensure_command_center_table
from cross_asset_regime_engine import _ensure_regime_snapshots_table
from market_intelligence_scanner import _ensure_scanner_snapshots_table


def test_command_center_snapshots_table_index():
    """Verify index on market_intelligence_command_snapshots timestamp."""
    conn = database.get_connection()
    try:
        _ensure_command_center_table(conn)
        cur = conn.cursor()
        cur.execute("PRAGMA index_list(market_intelligence_command_snapshots)")
        indices = [row[1] for row in cur.fetchall()]
        assert "idx_cmd_snapshots_ts" in indices
    finally:
        conn.close()


def test_regime_snapshots_table_index():
    """Verify index on market_regime_snapshots timestamp."""
    conn = database.get_connection()
    try:
        _ensure_regime_snapshots_table(conn)
        cur = conn.cursor()
        cur.execute("PRAGMA index_list(market_regime_snapshots)")
        indices = [row[1] for row in cur.fetchall()]
        assert "idx_regime_snapshots_ts" in indices
    finally:
        conn.close()


def test_scanner_snapshots_table_index():
    """Verify index on market_scanner_snapshots timestamp."""
    conn = database.get_connection()
    try:
        _ensure_scanner_snapshots_table(conn)
        cur = conn.cursor()
        cur.execute("PRAGMA index_list(market_scanner_snapshots)")
        indices = [row[1] for row in cur.fetchall()]
        assert "idx_scanner_snapshots_ts" in indices
    finally:
        conn.close()
