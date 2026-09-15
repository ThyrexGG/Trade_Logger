# -*- coding: utf-8 -*-
"""
Tests for the free-standing journal entries endpoint (`/api/operations/journal/entries`)
— market ideas/reviews/observations/plans not tied to a specific closed trade.
No prior test file covered this route directly (only the per-trade PATCH and
screenshot endpoints had coverage). Added alongside the "plan" kind (W14 —
Pre-Trade Checklist), which needed a fourth entry kind beyond the original
idea/review/observation set.
"""
from fastapi.testclient import TestClient

import database
from api.main import app

client = TestClient(app)


def _cleanup(entry_id: str) -> None:
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"DELETE FROM journal_entries WHERE id = {ph}", (entry_id,))
        conn.commit()
    finally:
        conn.close()


def test_create_and_list_a_plan_entry():
    r = client.post(
        "/api/operations/journal/entries",
        json={"kind": "plan", "instrument": "eurusd", "title": "LONG EURUSD plan", "body": "Thesis: ..."},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["kind"] == "plan"
    assert d["instrument"] == "EURUSD"  # normalized upper-case
    try:
        listed = client.get("/api/operations/journal/entries").json()
        assert any(e["id"] == d["id"] for e in listed["entries"])
    finally:
        _cleanup(d["id"])


def test_rejects_unknown_kind():
    r = client.post("/api/operations/journal/entries", json={"kind": "banana", "body": "x"})
    assert r.status_code == 422


def test_all_four_kinds_are_accepted():
    ids = []
    try:
        for kind in ("idea", "review", "observation", "plan"):
            r = client.post("/api/operations/journal/entries", json={"kind": kind, "body": f"a {kind}"})
            assert r.status_code == 200, (kind, r.text)
            assert r.json()["kind"] == kind
            ids.append(r.json()["id"])
    finally:
        for eid in ids:
            _cleanup(eid)
