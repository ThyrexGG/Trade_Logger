# -*- coding: utf-8 -*-
"""
A journal screenshot can be attached to a still-open position (the mobile app
and the web Journal both journal open trades). Regression: the upload guard only
knew closed trades and free-standing entries, so uploading to an open trade
returned 404 "No closed trade or journal entry".
"""
import pandas as pd

import database
from api.routers import operations


def _no_closed_trade(monkeypatch):
    monkeypatch.setattr(operations, "_fetch_journal_row", lambda _id: None)
    monkeypatch.setattr(database, "journal_entry_exists", lambda _id: False)


def test_open_position_is_a_valid_screenshot_owner(monkeypatch):
    _no_closed_trade(monkeypatch)
    df = pd.DataFrame([{"position_id": "CAP_abc123", "symbol": "US500"}])
    monkeypatch.setattr(database, "get_open_positions", lambda *a, **k: df)
    assert operations._journal_owner_exists("CAP_abc123") is True


def test_unknown_id_is_still_rejected(monkeypatch):
    _no_closed_trade(monkeypatch)
    df = pd.DataFrame([{"position_id": "CAP_abc123", "symbol": "US500"}])
    monkeypatch.setattr(database, "get_open_positions", lambda *a, **k: df)
    assert operations._journal_owner_exists("CAP_other") is False


def test_no_open_positions_is_rejected(monkeypatch):
    _no_closed_trade(monkeypatch)
    monkeypatch.setattr(database, "get_open_positions", lambda *a, **k: pd.DataFrame())
    assert operations._journal_owner_exists("CAP_abc123") is False


def test_open_position_lookup_failure_fails_closed(monkeypatch):
    _no_closed_trade(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(database, "get_open_positions", boom)
    assert operations._journal_owner_exists("CAP_abc123") is False
