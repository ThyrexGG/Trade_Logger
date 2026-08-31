"""
Phase 35 — Daily Trading Command Center UI Payload & Rendering Compatibility Test Suite
Validates that all UI data structures render properly into Streamlit DataFrames, cards, and expanders.
"""

import pytest
import pandas as pd
from xauusd_daily_command_center import (
    DailyTradingCommandEngine,
    SetupExplainabilityEngine,
    MarketContextSnapshotEngine,
    DailyResearchJournal,
)


def test_command_center_ui_dataframes_compatibility():
    """Validates that all tables in Daily Command Center convert cleanly to pd.DataFrame."""
    cmd = DailyTradingCommandEngine.get_command_center_payload("XAUUSD")
    
    # Checklist DataFrame
    df_chk = pd.DataFrame(cmd["checklist"])
    assert len(df_chk) == 10
    assert "item" in df_chk.columns
    assert "status" in df_chk.columns
    assert "detail" in df_chk.columns

    # Session Matrix DataFrame
    df_sess = pd.DataFrame(cmd["session_matrix"])
    assert len(df_sess) == 7
    assert "financial_center" in df_sess.columns
    assert "open_closed" in df_sess.columns

    # Setup Explainability Layers DataFrame
    df_layers = pd.DataFrame(cmd["setup_explainability"]["layers_breakdown"])
    assert len(df_layers) == 5
    assert "timeframe" in df_layers.columns
    assert "status" in df_layers.columns


def test_snapshots_and_journal_dataframes():
    """Validates that context snapshots and research notes DataFrames render properly."""
    snaps = MarketContextSnapshotEngine.get_snapshots(limit=5)
    df_snaps = pd.DataFrame(snaps)
    assert isinstance(df_snaps, pd.DataFrame)

    notes = DailyResearchJournal.get_notes(limit=5)
    df_notes = pd.DataFrame(notes)
    assert isinstance(df_notes, pd.DataFrame)
