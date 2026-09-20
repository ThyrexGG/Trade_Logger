# -*- coding: utf-8 -*-
"""Fix or delete a trade logged by hand — and nothing else. Runs on a throwaway sqlite DB."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import database
import tenant
from api.main import app

client = TestClient(app)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "manual.db")
    monkeypatch.setattr(database, "get_db_url", lambda: None)
    monkeypatch.setattr(database, "get_connection", lambda: sqlite3.connect(path, timeout=30))
    monkeypatch.setattr(database, "_PUSH_TABLES_READY", False)
    monkeypatch.setattr(database, "_DB_INITIALIZED", False)
    database.init_db(force=True)
    database.invalidate_db_cache()
    yield path


def _iso(delta):
    return (datetime.now(timezone.utc) + delta).isoformat()


def _body(**over):
    body = {
        "account_id": "OWN_MONEY", "symbol": "EURUSD", "direction": "BUY", "volume": 0.5,
        "entry_price": 1.08, "exit_price": 1.09, "commission": -1.0, "swap": 0.0, "gross_profit": 42.5,
        "entry_time": _iso(timedelta(days=-1, hours=-2)), "exit_time": _iso(timedelta(days=-1)),
        "setup_tag": "BREAKOUT", "notes": "first note",
    }
    body.update(over)
    return body


def _create(**over):
    r = client.post("/api/operations/journal/trades", json=_body(**over))
    assert r.status_code == 200, r.text
    return r.json()["trade_id"]


def _row(trade_id, uid):
    with tenant.use(uid):
        df = database.get_closed_trades()
    hit = df[df["trade_id"] == trade_id]
    return None if hit.empty else hit.iloc[0]


def test_edit_changes_the_trade_in_place_and_keeps_notes_and_screenshots(db):
    with tenant.use("alice"):
        tid = _create()
        database.add_journal_screenshot("shot1", tid, "shot.png", "image/png", 4, "iVBORw==", "cap")
        r = client.put(f"/api/operations/journal/trades/{tid}", json=_body(gross_profit=-12.0, symbol="gbpusd", setup_tag=None, notes=None))
        assert r.status_code == 200, r.text
        item = r.json()
        assert item["trade_id"] == tid
    row = _row(tid, "alice")
    assert row["symbol"] == "GBPUSD"
    assert float(row["gross_profit"]) == -12.0
    assert float(row["net_profit"]) == -13.0          # profit + commission + swap
    assert row["setup_tag"] in (None, "") or str(row["setup_tag"]) == "nan"
    assert "first note" in str(row.get("notes"))       # notes untouched when the edit sends none
    with tenant.use("alice"):
        assert len(database.list_journal_screenshots(tid)) == 1   # screenshot still attached


def test_edit_can_change_the_notes_and_rejects_bad_times(db):
    with tenant.use("alice"):
        tid = _create()
        ok = client.put(f"/api/operations/journal/trades/{tid}", json=_body(notes="new note"))
        assert ok.status_code == 200
        bad = client.put(f"/api/operations/journal/trades/{tid}", json=_body(entry_time=_iso(timedelta(hours=1)), exit_time=_iso(timedelta(hours=-1))))
        assert bad.status_code == 422
    assert "new note" in str(_row(tid, "alice").get("notes"))


def test_delete_removes_the_trade_and_its_screenshots(db):
    with tenant.use("alice"):
        tid = _create()
        database.add_journal_screenshot("shot2", tid, "s.png", "image/png", 4, "iVBORw==", None)
        r = client.delete(f"/api/operations/journal/trades/{tid}")
        assert r.status_code == 200 and r.json()["deleted"] is True
        assert client.delete(f"/api/operations/journal/trades/{tid}").status_code == 404
        assert database.list_journal_screenshots(tid) == []
    assert _row(tid, "alice") is None


def test_broker_synced_trades_cannot_be_edited_or_deleted(db):
    with tenant.use("alice"):
        database.save_closed_trades([{
            "trade_id": "CAP_12345", "account_id": "CAP", "symbol": "XAUUSD", "direction": "BUY", "volume": 1.0,
            "entry_price": 1.0, "exit_price": 2.0, "commission": 0.0, "swap": 0.0, "gross_profit": 5.0,
            "net_profit": 5.0, "entry_time": _iso(timedelta(days=-2)), "exit_time": _iso(timedelta(days=-2, hours=1)),
            "duration_minutes": 60.0, "setup_tag": None,
        }])
        assert client.delete("/api/operations/journal/trades/CAP_12345").status_code == 409
        assert client.put("/api/operations/journal/trades/CAP_12345", json=_body()).status_code == 409
    assert _row("CAP_12345", "alice") is not None


def test_another_users_trade_is_untouchable(db):
    with tenant.use("alice"):
        tid = _create()
    with tenant.use("mallory"):
        assert client.delete(f"/api/operations/journal/trades/{tid}").status_code == 404
        assert client.put(f"/api/operations/journal/trades/{tid}", json=_body(gross_profit=999.0)).status_code == 404
    row = _row(tid, "alice")
    assert row is not None and float(row["gross_profit"]) == 42.5
