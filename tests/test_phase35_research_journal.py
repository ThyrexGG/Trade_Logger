"""
Phase 35 — Daily Research Journal Notes & Persistence Test Suite
Validates persistent qualitative research observation notes without mutating trade records.
"""

import pytest
from datetime import datetime, timezone
from xauusd_daily_command_center import DailyResearchJournal


def test_daily_research_journal_add_and_retrieve():
    """Validates adding and retrieving persistent timestamped research notes."""
    note_text = "Phase 35 Test: Observed normal London/NY session overlap conditions."
    res = DailyResearchJournal.add_note(note_text=note_text, category="TEST_NOTE", session_context="LONDON/NY")
    assert isinstance(res, dict)
    assert "note_id" in res
    assert res["note_id"].startswith("NOTE_")
    assert res["note_text"] == note_text
    assert res["category"] == "TEST_NOTE"

    notes = DailyResearchJournal.get_notes(limit=10)
    assert len(notes) >= 1
    found = any(n["note_id"] == res["note_id"] for n in notes)
    assert found is True


def test_research_journal_preserves_trade_records():
    """Validates that saving research notes never mutates empirical trade tables."""
    from xauusd_forward_validator import XAUUSDForwardJournal
    before_df = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
    DailyResearchJournal.add_note("Another non-invasive test observation.")
    after_df = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
    assert len(before_df) == len(after_df)
