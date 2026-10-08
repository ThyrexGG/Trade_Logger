# -*- coding: utf-8 -*-
"""
Web links on notes and trades (TradingView ideas/charts, articles, videos).

Links live in `journal_links`, keyed by the owner id (a closed trade id or a
journal entry id) exactly like screenshots, so a broker re-sync never touches
them. Only http(s) URLs are accepted.
"""
from fastapi.testclient import TestClient

import database
import tenant
from api.main import app

client = TestClient(app)

TV = "https://www.tradingview.com/chart/EURUSD/abc123-London-sweep/"
NEWS = "https://www.forexfactory.com/news/12345"


def _manual_trade() -> str:
    r = client.post(
        "/api/operations/journal/trades",
        json={
            "account_id": "LINKS_TEST", "symbol": "EURUSD", "direction": "BUY",
            "volume": 0.1, "entry_price": 1.1, "exit_price": 1.101, "gross_profit": 10.0,
            "entry_time": "2026-10-01T08:00:00+00:00", "exit_time": "2026-10-01T09:00:00+00:00",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["trade_id"]


def _link_rows(owner_id: str) -> int:
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"SELECT COUNT(*) FROM journal_links WHERE trade_id = {ph}", (owner_id,))
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def test_note_links_create_list_replace_clear_and_delete():
    r = client.post(
        "/api/operations/journal/entries",
        json={"kind": "idea", "body": "London sweep idea",
              "links": [{"url": TV}, {"url": NEWS, "label": "  CPI preview  "}]},
    )
    assert r.status_code == 200, r.text
    entry = r.json()
    eid = entry["id"]
    try:
        assert entry["links"] == [{"url": TV, "label": None}, {"url": NEWS, "label": "CPI preview"}]

        listed = {e["id"]: e for e in client.get("/api/operations/journal/entries").json()["entries"]}
        assert [l["url"] for l in listed[eid]["links"]] == [TV, NEWS]

        # a PATCH with only links is valid, and replaces the list in the given order
        r = client.patch(f"/api/operations/journal/entries/{eid}", json={"links": [{"url": NEWS}, {"url": TV, "label": "Chart"}]})
        assert r.status_code == 200, r.text
        assert [l["url"] for l in r.json()["links"]] == [NEWS, TV]
        assert r.json()["body"] == "London sweep idea"  # untouched

        r = client.patch(f"/api/operations/journal/entries/{eid}", json={"links": []})
        assert r.status_code == 200
        assert r.json()["links"] == []
        assert _link_rows(eid) == 0

        client.patch(f"/api/operations/journal/entries/{eid}", json={"links": [{"url": TV}]})
        assert _link_rows(eid) == 1
    finally:
        assert client.delete(f"/api/operations/journal/entries/{eid}").status_code == 200
    assert _link_rows(eid) == 0  # deleting the note deletes its links


def test_only_web_links_are_accepted():
    for bad in ("javascript:alert(1)", "tradingview.com/chart/x", "ftp://example.com/a", "https://", "data:text/html,hi"):
        r = client.post("/api/operations/journal/entries", json={"body": "x", "links": [{"url": bad}]})
        assert r.status_code == 422, bad


def test_link_count_is_capped():
    r = client.post(
        "/api/operations/journal/entries",
        json={"body": "x", "links": [{"url": f"https://example.com/{i}"} for i in range(11)]},
    )
    assert r.status_code == 422


def test_trade_links_round_trip_and_follow_the_trade():
    tid = _manual_trade()
    try:
        r = client.patch(f"/api/operations/journal/{tid}", json={"links": [{"url": TV, "label": "Setup"}]})
        assert r.status_code == 200, r.text
        assert r.json()["entry"]["links"] == [{"url": TV, "label": "Setup"}]
        assert "links" in r.json()["updated_fields"]

        # links-only PATCH leaves the notes alone; a notes-only PATCH leaves the links alone
        client.patch(f"/api/operations/journal/{tid}", json={"notes": "clean entry"})
        journal = {e["trade_id"]: e for e in client.get("/api/operations/journal").json()["entries"]}
        assert journal[tid]["notes"] == "clean entry"
        assert journal[tid]["links"] == [{"url": TV, "label": "Setup"}]
    finally:
        assert client.delete(f"/api/operations/journal/trades/{tid}").status_code == 200
    assert _link_rows(tid) == 0  # deleting a hand-logged trade deletes its links


def test_another_accounts_trade_looks_missing():
    """The single-trade lookup behind the annotation PATCH is tenant-scoped:
    a trade id that belongs to someone else is a 404, and nothing is written."""
    with tenant.use("links-other-user"):
        other = database.add_manual_trade({
            "account_id": "OTHER", "symbol": "GBPUSD", "direction": "SELL", "volume": 0.1,
            "entry_price": 1.3, "exit_price": 1.29, "commission": 0.0, "swap": 0.0, "gross_profit": 5.0,
            "entry_time": "2026-10-02T08:00:00+00:00", "exit_time": "2026-10-02T09:00:00+00:00",
            "setup_tag": None, "notes": None,
        })
    try:
        r = client.patch(f"/api/operations/journal/{other}", json={"notes": "not mine", "links": [{"url": TV}]})
        assert r.status_code == 404
        assert _link_rows(other) == 0
    finally:
        with tenant.use("links-other-user"):
            database.delete_manual_trade(other)
