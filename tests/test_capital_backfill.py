# -*- coding: utf-8 -*-
"""
Full-history import for a Capital.com connection (capital_backfill.py).

Capital.com is faked -- nothing here touches the network or a real account.
The things worth pinning: the import asks for activity ONLY on days that had a
close (it is one request per day, so this is what keeps it light), a full page
of transactions is split rather than silently truncated, a failed slice saves
nothing, and the walk stops by itself once the history runs out.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import capital_backfill as cb
import database
import tenant
from api import broker_credentials as bc
from api.main import app

NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
CREDS = {"api_key": "fake-k", "email": "a@example.test", "password": "fake-pw",
         "account_id": "CAP1", "is_demo": True}


class _Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}

    def json(self):
        return self._body


class FakeCapital:
    """Stands in for requests.Session. ``txs`` / ``acts`` are what the 'broker' holds."""

    def __init__(self, txs, acts, activity_status=200):
        self.txs, self.acts, self.activity_status = txs, acts, activity_status
        self.activity_days = []
        self.tx_calls = []

    def __call__(self):                      # requests.Session()
        return self

    def post(self, url, **kw):
        return _Resp(200, headers={"CST": "c", "X-SECURITY-TOKEN": "t"})

    def get(self, url, headers=None, params=None, timeout=None):
        p = params or {}
        if url.endswith("/history/transactions"):
            self.tx_calls.append((p["from"], p["to"]))
            rows = [t for t in self.txs if p["from"] <= t["dateUtc"][:19] <= p["to"]]
            return _Resp(200, {"transactions": rows})
        if url.endswith("/history/activity"):
            self.activity_days.append(p["from"][:10])
            if self.activity_status != 200:
                return _Resp(self.activity_status)
            rows = [a for a in self.acts if p["from"] <= a["dateUTC"][:19] <= p["to"]]
            return _Resp(200, {"activities": rows})
        raise AssertionError(url)


def _tx(deal, when, size):
    return {"dealId": deal, "dateUtc": when, "size": str(size), "instrumentName": "Gold",
            "transactionType": "TRADE", "note": "Trade closed"}


def _acts(deal, opened, closed):
    return [
        {"dealId": deal, "dateUTC": opened, "epic": "GOLD",
         "details": {"direction": "BUY", "size": 1.0, "level": 2000.0}},
        {"dealId": deal, "dateUTC": closed, "epic": "GOLD",
         "details": {"direction": "SELL", "size": 1.0, "level": 2010.0, "openPrice": 2000.0}},
    ]


@pytest.fixture()
def clean(monkeypatch):
    database.init_db()
    conn = database.get_connection()
    cur = conn.cursor()
    ph = database.get_sql_placeholder(conn)
    for t in ("closed_trades", "raw_deals"):
        cur.execute(f"DELETE FROM {t} WHERE user_id IN ({ph})", ("alice",))
    conn.commit()
    conn.close()
    database.invalidate_db_cache()
    monkeypatch.setattr(cb.time, "sleep", lambda _s: None)
    yield
    database.invalidate_db_cache()


def _use(monkeypatch, fake):
    monkeypatch.setattr(cb.requests, "Session", fake)


def test_a_window_imports_its_trades_and_asks_activity_only_for_days_with_a_close(clean, monkeypatch):
    # closed on 2026-09-20; opened the evening before. Nothing else in the window.
    fake = FakeCapital(
        [_tx("D1", "2026-09-20T10:00:00", 25.5)],
        _acts("D1", "2026-09-19T21:00:00", "2026-09-20T10:00:00"),
    )
    _use(monkeypatch, fake)
    with tenant.use("alice"):
        out = cb.backfill_step(CREDS, before="2026-10-01T00:00:00", now=NOW)
        df = database.get_closed_trades()

    assert out["imported"] == 1 and out["done"] is False
    assert out["next_before"] == "2026-09-01T00:00:00"          # 30 days further back
    assert sorted(fake.activity_days) == ["2026-09-19", "2026-09-20"]   # not 30 requests
    assert list(df["trade_id"]) == ["D1"] and float(df.iloc[0]["net_profit"]) == 25.5
    assert list(df["account_id"]) == ["CAP1"]
    assert round(float(df.iloc[0]["duration_minutes"])) == 780


def test_quiet_windows_cost_no_activity_calls_and_the_walk_ends_by_itself(clean, monkeypatch):
    fake = FakeCapital([], [])
    _use(monkeypatch, fake)
    before, empty, steps = None, 0, 0
    with tenant.use("alice"):
        while True:
            out = cb.backfill_step(CREDS, before, empty, now=NOW)
            before, empty, steps = out["next_before"], out["empty_days"], steps + 1
            if out["done"]:
                break
        assert database.get_closed_trades().empty
    assert fake.activity_days == []
    assert steps == 6                      # 6 x 30 days = the 180-day stop rule


def test_a_full_page_of_transactions_is_split_not_truncated(clean, monkeypatch):
    # 500 rows in the wide window looks like a cut-off page -> ask again in halves.
    base = datetime(2026, 9, 20)
    many = [_tx(f"D{i}", (base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%S"), 1.0) for i in range(520)]
    fake = FakeCapital(many, [])
    original = fake.get

    def capped(url, headers=None, params=None, timeout=None):
        r = original(url, headers, params, timeout)
        if url.endswith("/history/transactions"):
            r._body = {"transactions": r._body["transactions"][:500]}
        return r

    fake.get = capped
    _use(monkeypatch, fake)
    with tenant.use("alice"):
        txs = cb._fetch_transactions(fake, "https://x", {}, NOW - timedelta(days=30), NOW)
    assert len(fake.tx_calls) >= 3                      # wide call + two halves
    assert len({t["dealId"] for t in txs}) > 500        # more than one page's worth came back


def test_a_failed_slice_saves_nothing_so_it_can_simply_be_retried(clean, monkeypatch):
    fake = FakeCapital(
        [_tx("D2", "2026-09-20T10:00:00", 5.0)],
        _acts("D2", "2026-09-20T08:00:00", "2026-09-20T10:00:00"),
        activity_status=500,
    )
    _use(monkeypatch, fake)
    with tenant.use("alice"):
        with pytest.raises(cb.BackfillError):
            cb.backfill_step(CREDS, before="2026-10-01T00:00:00", now=NOW)
        assert database.get_closed_trades().empty


def test_repeating_a_slice_does_not_duplicate_trades(clean, monkeypatch):
    fake = FakeCapital(
        [_tx("D3", "2026-09-20T10:00:00", 5.0)],
        _acts("D3", "2026-09-20T08:00:00", "2026-09-20T10:00:00"),
    )
    _use(monkeypatch, fake)
    with tenant.use("alice"):
        for _ in range(2):
            cb.backfill_step(CREDS, before="2026-10-01T00:00:00", now=NOW)
        assert len(database.get_closed_trades()) == 1


def test_the_walk_never_goes_past_the_history_floor(clean, monkeypatch):
    _use(monkeypatch, FakeCapital([], []))
    with tenant.use("alice"):
        out = cb.backfill_step(CREDS, before="2012-01-10T00:00:00", now=NOW)
    assert out["done"] is True and out["window_from"] == "2012-01-01T00:00:00"


def test_a_connection_without_an_account_id_is_refused(clean):
    with pytest.raises(cb.BackfillError):
        cb.backfill_step({**CREDS, "account_id": ""}, now=NOW)


# --- through the HTTP route ------------------------------------------------

@pytest.fixture()
def conn_id(monkeypatch):
    monkeypatch.setenv("TL_CREDENTIAL_ENC_KEY", bc.generate_key())
    bc.ensure_table()
    with tenant.use("local"):
        meta = bc.create_connection(
            secret={"api_key": "fake-k", "email": "a@example.test", "password": "fake-pw"},
            account_id="CAP1", is_demo=True,
        )
    yield meta["id"]
    with tenant.use("local"):
        bc.delete_connection(meta["id"])


def test_route_returns_the_slice_result_and_never_a_secret(conn_id, monkeypatch):
    monkeypatch.setattr(cb, "backfill_step", lambda creds, before, empty: {
        "imported": 3, "next_before": "2026-09-01T00:00:00", "empty_days": 0,
        "done": False, "window_from": "2026-09-01T00:00:00", "oldest_trade": None})
    r = TestClient(app).post(f"/api/connections/{conn_id}/backfill", json={})
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 3 and r.json()["ok"] is True
    assert "fake-pw" not in r.text


def test_route_reports_a_broker_failure_as_ok_false(conn_id, monkeypatch):
    def boom(creds, before, empty):
        raise cb.BackfillError("Capital.com login failed (401)")
    monkeypatch.setattr(cb, "backfill_step", boom)
    r = TestClient(app).post(f"/api/connections/{conn_id}/backfill", json={"before": "2026-09-01T00:00:00"})
    assert r.status_code == 200
    assert r.json()["ok"] is False and "401" in r.json()["detail"]
    assert r.json()["next_before"] == "2026-09-01T00:00:00"      # caller can resume from here


def test_route_refuses_when_the_server_is_already_busy(conn_id, monkeypatch):
    from api.routers import connections as route
    held = [route._backfill_slots.acquire(blocking=False) for _ in range(route._MAX_CONCURRENT_BACKFILLS)]
    try:
        r = TestClient(app).post(f"/api/connections/{conn_id}/backfill", json={})
        assert r.status_code == 429
    finally:
        for ok in held:
            if ok:
                route._backfill_slots.release()


def test_route_unknown_connection_is_404():
    assert TestClient(app).post("/api/connections/nope/backfill", json={}).status_code == 404
