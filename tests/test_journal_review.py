# -*- coding: utf-8 -*-
"""
Per-trade review answers: where the stop went and why the trade ended.

Stored in `journal_review` (off the closed_trades row, like journal_links) as
short codes from a fixed list, so the journal can later be grouped by them.
"" clears an answer; a field left out of a PATCH keeps its saved value.
"""
from fastapi.testclient import TestClient

import database
from api.main import app

client = TestClient(app)


def _manual_trade() -> str:
    r = client.post(
        "/api/operations/journal/trades",
        json={
            "account_id": "REVIEW_TEST", "symbol": "NDX100", "direction": "BUY",
            "volume": 1, "entry_price": 30960, "exit_price": 31020, "gross_profit": 60.0,
            "entry_time": "2026-10-07T14:10:00+00:00", "exit_time": "2026-10-07T14:40:00+00:00",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["trade_id"]


def _review_rows(trade_id: str) -> int:
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"SELECT COUNT(*) FROM journal_review WHERE trade_id = {ph}", (trade_id,))
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def _listed(trade_id: str) -> dict:
    return {e["trade_id"]: e for e in client.get("/api/operations/journal").json()["entries"]}[trade_id]


def test_review_fields_save_list_keep_clear_and_delete():
    tid = _manual_trade()
    try:
        assert _listed(tid)["stop_placement"] is None and _listed(tid)["exit_reason"] is None

        # a PATCH with only a review field is valid
        r = client.patch(f"/api/operations/journal/{tid}", json={"stop_placement": "second"})
        assert r.status_code == 200, r.text
        assert r.json()["entry"]["stop_placement"] == "second"
        assert r.json()["updated_fields"] == ["stop_placement"]

        # setting the other one keeps the first
        r = client.patch(f"/api/operations/journal/{tid}", json={"exit_reason": "partial_runner", "notes": "half at 1R"})
        entry = r.json()["entry"]
        assert (entry["stop_placement"], entry["exit_reason"], entry["notes"]) == ("second", "partial_runner", "half at 1R")
        assert _listed(tid)["exit_reason"] == "partial_runner"

        # "" clears one; clearing both removes the row
        r = client.patch(f"/api/operations/journal/{tid}", json={"stop_placement": ""})
        assert r.json()["entry"]["stop_placement"] is None
        assert r.json()["entry"]["exit_reason"] == "partial_runner"
        client.patch(f"/api/operations/journal/{tid}", json={"exit_reason": ""})
        assert _review_rows(tid) == 0

        client.patch(f"/api/operations/journal/{tid}", json={"exit_reason": "cut_early"})
        assert _review_rows(tid) == 1
    finally:
        assert client.delete(f"/api/operations/journal/trades/{tid}").status_code == 200
    assert _review_rows(tid) == 0  # deleting the trade deletes its answers


def test_only_listed_answers_are_accepted():
    tid = _manual_trade()
    try:
        for body in ({"stop_placement": "wherever"}, {"exit_reason": "TARGET"}, {"exit_reason": 3}):
            r = client.patch(f"/api/operations/journal/{tid}", json=body)
            assert r.status_code == 422, (body, r.text)
        assert _review_rows(tid) == 0
    finally:
        client.delete(f"/api/operations/journal/trades/{tid}")
