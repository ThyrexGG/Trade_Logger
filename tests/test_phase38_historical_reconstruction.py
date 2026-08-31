"""
Phase 38 — Historical News Reconstruction Engine Test Suite
Validates lookahead-free historical reconstruction of economic events, holidays, sessions, and market data breadth.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_news_history_audit import HistoricalContextReconstructor, HistoricalEconomicEvent


def test_reconstruct_date_context_structure():
    """Validates complete market context payload for a target date."""
    target_dt = date(2026, 9, 1)
    recon = HistoricalContextReconstructor.reconstruct_date_context(target_dt)

    assert isinstance(recon, dict)
    assert recon["target_date"] == "2026-09-01"
    assert "events" in recon
    assert "holiday_audit" in recon
    assert "sessions" in recon
    assert "market_data_breadth" in recon
    assert "information_partition" in recon
    assert "day_fingerprint" in recon
    assert len(recon["day_fingerprint"]) == 64


def test_events_reconstruction_and_fingerprints():
    """Validates event reconstruction fields and SHA-256 fingerprint generation."""
    target_dt = date(2026, 9, 1)
    recon = HistoricalContextReconstructor.reconstruct_date_context(target_dt)
    events = recon["events"]

    assert len(events) >= 1
    for ev in events:
        assert "event_id" in ev
        assert "event_name" in ev
        assert "currency" in ev
        assert "impact" in ev
        assert "scheduled_timestamp" in ev
        assert "data_fingerprint" in ev
        assert len(ev["data_fingerprint"]) == 64


def test_holiday_reconstruction_seven_centers():
    """Validates 7 financial centers holiday audit on target date."""
    target_dt = date(2026, 9, 1)
    recon = HistoricalContextReconstructor.reconstruct_date_context(target_dt)
    hol_audit = recon["holiday_audit"]

    assert "all_centers" in hol_audit
    assert len(hol_audit["all_centers"]) == 7
    centers = [c["center"] for c in hol_audit["all_centers"]]
    assert any("London" in c for c in centers)
    assert any("New York" in c for c in centers)
    assert any("Tokyo" in c for c in centers)


def test_session_reconstruction_five_blocks():
    """Validates reconstruction of 5 operational trading session blocks."""
    target_dt = date(2026, 9, 1)
    recon = HistoricalContextReconstructor.reconstruct_date_context(target_dt)
    sessions = recon["sessions"]

    assert len(sessions) == 5
    sess_names = [s["session_name"] for s in sessions]
    assert "ASIA" in sess_names
    assert "LONDON" in sess_names
    assert "NEW_YORK" in sess_names
    assert "LONDON_NY_OVERLAP" in sess_names
    assert "ROLLOVER" in sess_names
