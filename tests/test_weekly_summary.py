# -*- coding: utf-8 -*-
"""Weekly performance summary: what it says, when it goes out, that it goes out once, and that it stays per user."""
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import database
import tenant
from api import weekly_summary as ws
from api.main import app

client = TestClient(app)

MON = date(2026, 9, 14)                                          # a Monday
SUN_NOON = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)      # the send moment for the week of MON


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "weekly.db")
    monkeypatch.setenv("TL_PUSH_ENABLED", "0")
    monkeypatch.setattr(database, "get_db_url", lambda: None)
    monkeypatch.setattr(database, "get_connection", lambda: sqlite3.connect(path, timeout=30))
    monkeypatch.setattr(database, "_PUSH_TABLES_READY", False)
    monkeypatch.setattr(database, "_DB_INITIALIZED", False)
    database.init_db(force=True)
    database.invalidate_db_cache()
    ws._handled.clear()
    yield path
    ws._handled.clear()


def _trade(pnl, day_offset=0, symbol="EURUSD", tag=None, account="ACC1", hour=10):
    """A manual closed trade exiting `day_offset` days after MON at `hour`:00 UTC."""
    exit_t = datetime.combine(MON + timedelta(days=day_offset), datetime.min.time(), tzinfo=timezone.utc).replace(hour=hour)
    database.add_manual_trade({
        "account_id": account, "symbol": symbol, "direction": "BUY", "volume": 1.0, "entry_price": 1.0,
        "exit_price": 1.0, "commission": 0.0, "swap": 0.0, "gross_profit": pnl,
        "entry_time": (exit_t - timedelta(minutes=5)).isoformat(), "exit_time": exit_t.isoformat(), "setup_tag": tag,
    })


def _events():
    return [e for e in database.list_trade_events(after_id=0, limit=100) if e["kind"] == "summary"]


def test_summary_numbers_and_message(db):
    with tenant.use("alice"):
        _trade(100, 0, "XAUUSD", "BREAKOUT")
        _trade(50, 1, "EURUSD", "BREAKOUT")
        _trade(-40, 2, "US500", "NEWS SCALP")
        _trade(-10, 4, "EURUSD")
        _trade(999, 8, "XAUUSD", "OUTSIDE")      # the following week: must not count
        _trade(999, -1, "XAUUSD", "OUTSIDE")     # the previous week: must not count
        s = ws.summarize(MON)
        assert (s["trades"], s["wins"], s["losses"], s["net"]) == (4, 2, 2, 100.0)
        assert s["win_rate"] == 0.5 and s["profit_factor"] == 3.0
        assert s["best_trade"] == {"symbol": "XAUUSD", "net": 100.0}
        assert s["worst_trade"] == {"symbol": "US500", "net": -40.0}
        assert s["best_tag"] == {"tag": "BREAKOUT", "net": 150.0, "trades": 2}
        assert s["worst_tag"] is None                # NEWS SCALP has only one trade: too few to call
        assert s["untagged"] == 1
        assert [d["net"] for d in s["by_day"]] == [100.0, 50.0, -40.0, 0.0, -10.0, 0.0, 0.0]
        title, body = ws.message(s)
        assert title == "Your week: +$100.00 on 4 trades"
        assert "2 won, 2 lost (50% win rate)" in body and "Best: XAUUSD +$100.00" in body
        assert "Worst: US500 -$40.00" in body and "Best setup: BREAKOUT +$150.00 over 2" in body


def test_empty_week_has_zeroed_summary_and_sends_nothing(db):
    with tenant.use("alice"):
        s = ws.summarize(MON)
        assert s["trades"] == 0 and s["win_rate"] is None and s["best_trade"] is None
        assert ws.check(now=SUN_NOON) == 0 and _events() == []


def test_sent_once_on_sunday_noon_and_never_again(db):
    with tenant.use("alice"):
        _trade(60, 1)
        assert ws.check(now=SUN_NOON - timedelta(minutes=1)) == 0      # not yet
        assert ws.check(now=SUN_NOON) == 1
        assert ws.check(now=SUN_NOON + timedelta(hours=3)) == 0        # already sent
        ws._handled.clear()                                             # a server restart forgets the memo...
        assert ws.check(now=SUN_NOON + timedelta(hours=6)) == 0        # ...the event key still blocks a repeat
        (e,) = _events()
        assert e["title"] == "Your week: +$60.00 on 1 trade" and e["ref_id"] == "2026-W38"


def test_missed_summary_is_sent_late_but_not_after_the_grace_window(db):
    with tenant.use("alice"):
        _trade(25, 2)
        monday_after = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
        assert ws.check(now=monday_after) == 1                          # server was asleep on Sunday: sent Monday
    with tenant.use("bob"):
        _trade(25, 2)
        too_late = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)      # Thursday: stale, skipped
        assert ws.check(now=too_late) == 0


def test_a_trade_that_closes_after_an_empty_first_check_is_still_included(db):
    with tenant.use("alice"):
        assert ws.check(now=SUN_NOON) == 0
        _trade(-30, 6, hour=20)                                          # Sunday evening
        assert ws.check(now=SUN_NOON + timedelta(hours=9)) == 1
        assert _events()[0]["title"] == "Your week: -$30.00 on 1 trade"


def test_can_be_switched_off_and_is_per_user(db):
    with tenant.use("alice"):
        _trade(10, 1)
        ws.set_enabled(False)
        assert ws.is_enabled() is False and ws.check(now=SUN_NOON) == 0
    with tenant.use("bob"):
        _trade(20, 1)
        assert ws.is_enabled() is True and ws.check(now=SUN_NOON) == 1
        assert [e["title"] for e in _events()] == ["Your week: +$20.00 on 1 trade"]
    with tenant.use("alice"):
        assert _events() == []
        ws.set_enabled(True)
        assert ws.check(now=SUN_NOON) == 1
        assert [e["title"] for e in _events()] == ["Your week: +$10.00 on 1 trade"]


def test_quiet_outside_the_window_without_touching_the_database(db, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not read trades on a Friday")
    monkeypatch.setattr(database, "get_closed_trades", boom)
    friday = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    with tenant.use("alice"):
        assert ws.check(now=friday) == 0
        assert ws.weeks_due(friday) == []


def test_users_with_a_phone_are_watched_by_the_background_loop(db):
    from api import sync_service
    with tenant.use("alice"):
        database.upsert_push_device("ExponentPushToken[abcdefghijkl]", platform="android")
    assert "alice" in sync_service._alert_user_ids()


def test_endpoint_returns_this_and_last_week_and_toggles(db):
    r = client.get("/api/weekly-summary")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True and len(body["weeks"]) == 2
    assert body["weeks"][0]["is_current"] is True and body["weeks"][1]["is_current"] is False
    assert body["weeks"][0]["summary"]["trades"] == 0 and len(body["weeks"][0]["summary"]["by_day"]) == 7
    assert client.put("/api/weekly-summary", json={"enabled": False}).json() == {"enabled": False}
    assert client.get("/api/weekly-summary").json()["enabled"] is False
    assert client.put("/api/weekly-summary", json={"enabled": "maybe"}).status_code == 422
    assert client.put("/api/weekly-summary", json={"enabled": True, "extra": 1}).status_code == 422


def test_tag_stats_reports_untagged_trades(db):
    with tenant.use("alice"):
        _trade(10, 0, tag="BREAKOUT")
        _trade(-5, 1)
        _trade(7, 2)
        database.invalidate_db_cache()
        from api.routers import operations
        out = operations.journal_tag_stats()
    assert out["total_trades"] == 3
    assert out["untagged"] == {"n": 2, "net_total": 2.0}
    assert [t["tag"] for t in out["tags"]] == ["BREAKOUT"]
