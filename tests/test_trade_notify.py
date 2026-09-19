# -*- coding: utf-8 -*-
"""
Trade open/close events -> Expo push + the event feed the desktop app polls.

Runs against a throwaway sqlite file (never the developer's real database) and
a fake Expo endpoint (never the network).
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import database
import tenant
import trade_notify
from api.main import app

client = TestClient(app)


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%dT%H:%M:%S")


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "notify.db")
    monkeypatch.setattr(database, "get_db_url", lambda: None)
    monkeypatch.setattr(database, "get_connection", lambda: sqlite3.connect(path, timeout=30))
    monkeypatch.setattr(database, "_PUSH_TABLES_READY", False)
    monkeypatch.setattr(database, "_DB_INITIALIZED", False)
    database.init_db(force=True)
    database.invalidate_db_cache()
    return path


class _SyncThread:
    """Runs the target immediately so tests don't race a background thread."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


@pytest.fixture()
def sent(monkeypatch):
    """Capture pushes instead of calling Expo."""
    calls = []
    monkeypatch.setattr(trade_notify.threading, "Thread", _SyncThread)
    monkeypatch.setattr(
        trade_notify, "send_pushes",
        lambda tokens, title, body, data, user_id=None: calls.append((tokens, title, body, data, user_id)) or [],
    )
    return calls


def _pos(pid="CAP_1", opened=None, **kw):
    return {"position_id": pid, "symbol": "us500", "direction": "BUY", "volume": 0.5,
            "entry_price": 6500.25, "open_time": _iso(timedelta(minutes=-1)) if opened is None else opened, **kw}


def _trade(tid="1", exit_time=None, **kw):
    return {"trade_id": tid, "symbol": "US500", "direction": "SELL", "volume": 0.85,
            "exit_price": 6490.0, "net_profit": 32.1, "duration_minutes": 95.0,
            "exit_time": exit_time or _iso(timedelta(minutes=-2)), **kw}


# --- event recording ---------------------------------------------------------

def test_opened_event_is_recorded_once(db):
    with tenant.use("alice"):
        first = trade_notify.record_opened(_pos())
        again = trade_notify.record_opened(_pos())
        events = database.list_trade_events()
    assert first is not None and again is None
    assert len(events) == 1
    assert events[0]["title"] == "US500 BUY opened"
    assert events[0]["body"] == "0.5 @ 6500.25"
    assert events[0]["kind"] == "opened"


def test_old_or_undated_positions_stay_silent(db):
    with tenant.use("alice"):
        assert trade_notify.record_opened(_pos("CAP_old", opened=_iso(timedelta(hours=-5)))) is None
        assert trade_notify.record_opened(_pos("CAP_none", opened="")) is None
        assert trade_notify.record_opened(_pos("CAP_bad", opened="not a date")) is None
        assert database.list_trade_events() == []


def test_closed_event_title_carries_the_pnl(db):
    with tenant.use("alice"):
        eid = trade_notify.record_closed(_trade())
        loss = trade_notify.record_closed(_trade("2", net_profit=-12.5))
        events = database.list_trade_events()
    assert eid is not None and loss is not None
    assert events[0]["title"] == "US500 closed +$32.10"
    assert events[0]["body"] == "SELL 0.85 · held 1.6h"
    assert events[1]["title"] == "US500 closed -$12.50"


def test_history_backfill_does_not_notify(db):
    with tenant.use("alice"):
        assert trade_notify.record_closed(_trade("h1", exit_time="2025-01-02T00:00:00")) is None
        assert database.list_trade_events() == []


def test_partial_close_ids_are_distinct_events(db):
    # capital_sync gives a partial close the id "<dealId>_1"; each is its own event.
    with tenant.use("alice"):
        assert trade_notify.record_closed(_trade("D1")) is not None
        assert trade_notify.record_closed(_trade("D1_1")) is not None
        assert len(database.list_trade_events()) == 2


def test_events_are_tenant_isolated_and_ordered(db):
    with tenant.use("alice"):
        trade_notify.record_opened(_pos("CAP_a"))
        trade_notify.record_closed(_trade("a"))
    with tenant.use("bob"):
        assert database.list_trade_events() == []
        assert database.latest_trade_event_id() == 0
        trade_notify.record_opened(_pos("CAP_b"))
    with tenant.use("alice"):
        evs = database.list_trade_events()
        assert [e["kind"] for e in evs] == ["opened", "closed"]
        assert evs[0]["id"] < evs[1]["id"]
        assert [e["kind"] for e in database.list_trade_events(after_id=evs[0]["id"])] == ["closed"]
        assert database.latest_trade_event_id() == evs[1]["id"]


# --- delivery ------------------------------------------------------------------

def test_new_event_pushes_to_registered_devices_only(db, sent):
    with tenant.use("alice"):
        database.upsert_push_device("ExponentPushToken[aaa]", "android", "Pixel")
    with tenant.use("bob"):
        database.upsert_push_device("ExponentPushToken[bbb]", "android", "Other")
    with tenant.use("alice"):
        trade_notify.record_closed(_trade())
        trade_notify.record_closed(_trade())  # duplicate -> no second push
    assert len(sent) == 1
    tokens, title, body, data, uid = sent[0]
    assert tokens == ["ExponentPushToken[aaa]"]
    assert title == "US500 closed +$32.10"
    assert data["kind"] == "closed" and data["ref_id"] == "1"
    assert uid == "alice"


def test_no_devices_means_no_push_but_event_is_logged(db, sent):
    with tenant.use("alice"):
        trade_notify.record_opened(_pos())
        assert len(database.list_trade_events()) == 1
    assert sent == []


def test_kill_switch_logs_event_without_pushing(db, sent, monkeypatch):
    monkeypatch.setenv("TL_PUSH_ENABLED", "0")
    with tenant.use("alice"):
        database.upsert_push_device("ExponentPushToken[aaa]")
        trade_notify.record_opened(_pos())
        assert len(database.list_trade_events()) == 1
    assert sent == []


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._p


def test_expo_payload_shape_and_unregistered_device_is_pruned(db, monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, body=json, timeout=timeout)
        return _Resp({"data": [
            {"status": "ok", "id": "x"},
            {"status": "error", "message": "gone", "details": {"error": "DeviceNotRegistered"}},
        ]})

    monkeypatch.setattr(trade_notify.requests, "post", fake_post)
    with tenant.use("alice"):
        database.upsert_push_device("ExponentPushToken[live]")
        database.upsert_push_device("ExponentPushToken[dead]")
        trade_notify.send_pushes(["ExponentPushToken[live]", "ExponentPushToken[dead]"],
                                 "T", "B", {"kind": "closed"}, user_id="alice")
        left = [d["token"] for d in database.list_push_devices()]
    assert captured["url"] == trade_notify.EXPO_PUSH_URL
    assert captured["timeout"] == 8
    assert captured["body"][0] == {"to": "ExponentPushToken[live]", "title": "T", "body": "B",
                                   "data": {"kind": "closed"}, "sound": "default",
                                   "priority": "high", "channelId": "trades"}
    assert left == ["ExponentPushToken[live]"]


def test_expo_outage_never_raises(db, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("expo down")

    monkeypatch.setattr(trade_notify.requests, "post", boom)
    assert trade_notify.send_pushes(["ExponentPushToken[x]"], "T", "B", {}) == []


# --- hooks ---------------------------------------------------------------------

def test_save_open_positions_emits_opened_only_for_new_positions(db):
    fresh = _pos("CAP_new")
    row = {"account_id": "ACC", "sl": 0, "tp": 0, "current_price": 6500.0, "floating_pnl": 0.0,
           "swap": 0.0, "updated_at": _iso(timedelta(0))}
    with tenant.use("alice"):
        database.save_open_positions("ACC", [{**row, **fresh}])
        assert [e["ref_id"] for e in database.list_trade_events()] == ["CAP_new"]
        # next sync: same position still open -> no second event
        database.save_open_positions("ACC", [{**row, **fresh}])
        assert len(database.list_trade_events()) == 1
        # a stale position appearing (e.g. first sync of an old account) stays silent
        database.save_open_positions("ACC", [{**row, **fresh}, {**row, **_pos("CAP_old", opened=_iso(timedelta(days=-3)))}])
        assert len(database.list_trade_events()) == 1


def test_notification_failure_never_breaks_open_position_save(db, monkeypatch):
    def boom(_pos):
        raise RuntimeError("notify exploded")

    monkeypatch.setattr(trade_notify, "record_opened", boom)
    row = {"account_id": "ACC", "sl": 0, "tp": 0, "current_price": 1.0, "floating_pnl": 0.0,
           "swap": 0.0, "updated_at": _iso(timedelta(0))}
    with tenant.use("alice"):
        database.save_open_positions("ACC", [{**row, **_pos("CAP_x")}])
        assert len(database.get_open_positions()) == 1


# --- HTTP API ------------------------------------------------------------------

def test_register_rejects_non_expo_tokens(db):
    assert client.post("/api/push/register", json={"token": "not-a-token-at-all"}).status_code == 422
    assert client.post("/api/push/register", json={"token": "ExponentPushToken[abc]", "extra": 1}).status_code == 422


def test_register_unregister_roundtrip(db):
    body = {"token": "ExponentPushToken[abc123]", "platform": "android", "device_name": "Pixel 8"}
    r = client.post("/api/push/register", json=body)
    assert r.status_code == 200 and r.json()["devices"] == 1
    assert client.post("/api/push/register", json=body).json()["devices"] == 1  # idempotent
    r = client.post("/api/push/unregister", json={"token": "ExponentPushToken[abc123]"})
    assert r.json() == {**r.json(), "removed": True, "devices": 0}


def test_events_endpoint_baseline_then_incremental(db):
    r = client.get("/api/push/events").json()
    assert r["events"] == [] and r["latest_id"] == 0
    tenant_id = tenant.LOCAL_USER_ID
    with tenant.use(tenant_id):
        trade_notify.record_closed(_trade("e1"))
        trade_notify.record_closed(_trade("e2", net_profit=-5.0))
    base = client.get("/api/push/events").json()
    assert base["events"] == [] and base["latest_id"] == 2  # no after_id -> baseline only, no replay
    all_ev = client.get("/api/push/events", params={"after_id": 0}).json()["events"]
    assert [e["ref_id"] for e in all_ev] == ["e1", "e2"]
    nxt = client.get("/api/push/events", params={"after_id": all_ev[0]["id"]}).json()["events"]
    assert [e["ref_id"] for e in nxt] == ["e2"]


def test_test_push_reports_expo_answer(db, monkeypatch):
    r = client.post("/api/push/test").json()
    assert r["sent"] == 0 and "No device" in r["error"]

    client.post("/api/push/register", json={"token": "ExponentPushToken[abc123]"})
    monkeypatch.setattr(trade_notify.requests, "post",
                        lambda *a, **k: _Resp({"data": [{"status": "error", "message": "InvalidCredentials",
                                                        "details": {"error": "InvalidCredentials"}}]}))
    r = client.post("/api/push/test").json()
    assert r["sent"] == 0 and "InvalidCredentials" in r["error"]

    monkeypatch.setattr(trade_notify.requests, "post",
                        lambda *a, **k: _Resp({"data": [{"status": "ok", "id": "1"}]}))
    r = client.post("/api/push/test").json()
    assert r["sent"] == 1 and r["error"] is None


# --- sync-cycle hook -------------------------------------------------------------

def test_sync_cycle_records_closed_trades_and_survives_a_failing_recorder(monkeypatch):
    """auto_sync.run_sync_cycle must call record_closed for each *new* closed trade,
    before the legacy alert channels, and a recorder crash must not fail the cycle."""
    import pandas as pd
    import auto_sync

    df = pd.DataFrame([_trade("T1"), _trade("T2")])
    monkeypatch.setattr(auto_sync.capital_sync, "sync_capital", lambda creds=None: True)
    monkeypatch.setattr(auto_sync.database, "get_closed_trades", lambda *a, **k: df)
    monkeypatch.setattr(auto_sync.database, "get_active_price_alerts", lambda: [])
    legacy = []
    monkeypatch.setattr(auto_sync.alerts, "notify_trade_closed", lambda row: legacy.append(row["trade_id"]))
    recorded = []
    monkeypatch.setattr(trade_notify, "record_closed", lambda row: recorded.append(row["trade_id"]))

    known = {"T1"}  # T1 was already seen by an earlier cycle
    result = auto_sync.run_sync_cycle(known, logfn=lambda _m: None)
    assert recorded == ["T2"] and legacy == ["T2"]
    assert result["new_closed_trades"] == 1 and result["errors"] == []

    def boom(_row):
        raise RuntimeError("recorder exploded")

    monkeypatch.setattr(trade_notify, "record_closed", boom)
    result = auto_sync.run_sync_cycle(set(), logfn=lambda _m: None)
    assert result["errors"] == []          # the failure is contained...
    assert legacy[1:] == ["T1", "T2"]      # ...and the existing alert channels still ran for both


# --- price alerts -------------------------------------------------------------

def test_price_alert_event_is_recorded_once_and_pushed(db, sent):
    with tenant.use("alice"):
        database.upsert_push_device("ExponentPushToken[abc]", "android", "Pixel")
        first = trade_notify.record_price_alert("xauusd", 2401.5, 2400, "ABOVE", 7)
        again = trade_notify.record_price_alert("xauusd", 2402.0, 2400, "ABOVE", 7)
        events = database.list_trade_events()
    assert first is not None and again is None
    assert len(events) == 1
    assert events[0]["kind"] == "alert"
    assert events[0]["title"] == "XAUUSD price alert"
    assert events[0]["body"] == "XAUUSD is 2401.5, above your 2400 target"
    assert len(sent) == 1 and sent[0][3]["kind"] == "alert" and sent[0][3]["ref_id"] == "7"


def test_price_alert_below_wording_and_bad_input(db):
    with tenant.use("alice"):
        assert trade_notify.record_price_alert("EURUSD", 1.0801, 1.081, "BELOW", 9) is not None
        assert database.list_trade_events()[0]["body"] == "EURUSD is 1.0801, below your 1.081 target"
        assert trade_notify.record_price_alert("EURUSD", 1.0, 1.0, "BELOW", None) is None
