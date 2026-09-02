# -*- coding: utf-8 -*-
"""
Tests for Stage 12 — Journal edit migration.

`PATCH /api/operations/journal/{trade_id}` migrates the legacy Streamlit
"Log & Review Trade Setup" workflow (`database.update_trade_journal`) to an
HTTP surface consumed by the React SPA. Only the subjective annotation fields
(`setup_tag`, `notes`, `chart_snapshot_url`) are writable; every execution /
trade fact is immutable, and the endpoint touches no broker / execution path.
"""
import pytest
from fastapi.testclient import TestClient

import database
from api.main import app

client = TestClient(app)

EDITABLE = ("setup_tag", "notes", "chart_snapshot_url")
IMMUTABLE_SAMPLE = {
    "symbol": "FAKE/USD",
    "direction": "SELL",
    "entry_price": 99999.0,
    "exit_price": 1.0,
    "volume": 777.0,
    "net_profit": 123456.0,
    "trade_id": "hacked",
    "account_id": "ATTACKER",
    "exit_time": "1970-01-01T00:00:00",
    "rating": 5,
}


@pytest.fixture()
def trade_id():
    """A real closed trade whose annotation fields are snapshotted and restored."""
    df = database.get_closed_trades()
    if df.empty:
        pytest.skip("no closed trades to exercise the journal edit endpoint")
    row = df.iloc[0]
    tid = str(row["trade_id"])
    before = {
        f: (None if row.get(f) is None or str(row.get(f)) == "nan" else str(row.get(f)))
        for f in EDITABLE
    }
    yield tid
    # restore the exact original annotation values, NULLs included
    conn = database.get_connection()
    try:
        ph = "%s" if database.is_postgres() else "?"
        conn.cursor().execute(
            f"UPDATE closed_trades SET {', '.join(f + ' = ' + ph for f in EDITABLE)} "
            f"WHERE trade_id = {ph}",
            (*(before[f] for f in EDITABLE), tid),
        )
        conn.commit()
    finally:
        conn.close()
    database.invalidate_db_cache("closed_trades")


def _immutable_snapshot(tid: str) -> dict:
    df = database.get_closed_trades()
    r = df[df["trade_id"] == tid].iloc[0]
    keys = ["symbol", "direction", "entry_price", "exit_price", "volume",
            "commission", "swap", "gross_profit", "net_profit", "entry_time",
            "exit_time", "duration_minutes", "account_id"]
    return {k: str(r.get(k)) for k in keys}


# 1. successful journal update -------------------------------------------------
def test_successful_update_returns_authoritative_record(trade_id):
    r = client.patch(
        f"/api/operations/journal/{trade_id}",
        json={"setup_tag": "BREAKOUT", "notes": "clean London break", "chart_snapshot_url": "https://tv/x/abc"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["entry"]["trade_id"] == trade_id
    assert d["entry"]["setup_tag"] == "BREAKOUT"
    assert d["entry"]["notes"] == "clean London break"
    assert d["entry"]["chart_snapshot_url"] == "https://tv/x/abc"
    assert set(d["updated_fields"]) == {"setup_tag", "notes", "chart_snapshot_url"}
    assert d["writable"] is True
    assert d["live_broker_transmission"] == "BLOCKED"


def test_partial_update_only_touches_named_fields(trade_id):
    client.patch(f"/api/operations/journal/{trade_id}", json={"setup_tag": "TREND", "notes": "keep me"})
    r = client.patch(f"/api/operations/journal/{trade_id}", json={"notes": "changed"})
    assert r.status_code == 200
    d = r.json()
    assert d["entry"]["notes"] == "changed"
    assert d["entry"]["setup_tag"] == "TREND"
    assert d["updated_fields"] == ["notes"]


# 2. unknown trade -> 404 -----------------------------------------------------
def test_unknown_trade_is_404():
    r = client.patch("/api/operations/journal/NON_EXISTENT_TRADE_XYZ", json={"notes": "x"})
    assert r.status_code == 404


# 3. invalid payload -> validation failure ----------------------------------
def test_empty_payload_is_rejected(trade_id):
    assert client.patch(f"/api/operations/journal/{trade_id}", json={}).status_code == 422


def test_all_null_payload_is_rejected(trade_id):
    r = client.patch(
        f"/api/operations/journal/{trade_id}",
        json={"setup_tag": None, "notes": None, "chart_snapshot_url": None},
    )
    assert r.status_code == 422


def test_oversized_setup_tag_is_rejected(trade_id):
    r = client.patch(f"/api/operations/journal/{trade_id}", json={"setup_tag": "X" * 200})
    assert r.status_code == 422


# 4. unsupported field rejected --------------------------------------------
@pytest.mark.parametrize("field,value", list(IMMUTABLE_SAMPLE.items()))
def test_unsupported_field_rejected(trade_id, field, value):
    r = client.patch(f"/api/operations/journal/{trade_id}", json={"notes": "ok", field: value})
    assert r.status_code == 422, f"{field} should be rejected as an unknown field"


# 5. immutable trade fields cannot be modified ----------------------------
def test_immutable_fields_unchanged_after_edit(trade_id):
    before = _immutable_snapshot(trade_id)
    r = client.patch(
        f"/api/operations/journal/{trade_id}",
        json={"setup_tag": "LIQUIDITY GRAB", "notes": "annotation only"},
    )
    assert r.status_code == 200
    after = _immutable_snapshot(trade_id)
    assert before == after
    # and the returned record's execution facts still match the table
    e = r.json()["entry"]
    assert str(e["net_profit"]) == before["net_profit"] or float(e["net_profit"]) == float(before["net_profit"])
    assert e["symbol"].upper() == before["symbol"].upper()


# 6. persisted value is returned correctly -------------------------------
def test_persisted_value_round_trips(trade_id):
    client.patch(f"/api/operations/journal/{trade_id}", json={"notes": "persisted-marker-42"})
    df = database.get_closed_trades()
    row = df[df["trade_id"] == trade_id].iloc[0]
    assert str(row["notes"]) == "persisted-marker-42"


# 7. subsequent GET reflects the update --------------------------------
def test_subsequent_get_reflects_update(trade_id):
    client.patch(f"/api/operations/journal/{trade_id}", json={"setup_tag": "NEWS SCALP", "notes": "GET-should-see-this"})
    d = client.get("/api/operations/journal").json()
    entry = next(e for e in d["entries"] if e["trade_id"] == trade_id)
    assert entry["setup_tag"] == "NEWS SCALP"
    assert entry["notes"] == "GET-should-see-this"
    assert d["writable"] is True


# 8. endpoint cannot trigger execution / broker behavior --------------
def test_edit_does_not_change_safety_state(trade_id):
    before = client.get("/api/operations/system").json()
    client.patch(f"/api/operations/journal/{trade_id}", json={"notes": "no execution here"})
    after = client.get("/api/operations/system").json()
    assert after["live_automation_enabled"] is False
    assert after["live_broker_transmission"] == "BLOCKED"
    assert before["open_positions"] == after["open_positions"]


def test_edit_does_not_write_execution_orders(trade_id):
    a = client.get("/api/operations/audit?limit=1").json()
    client.patch(f"/api/operations/journal/{trade_id}", json={"notes": "still no orders"})
    b = client.get("/api/operations/audit?limit=1").json()
    assert a["total_records"] == b["total_records"]
    assert a["mode_counts"] == b["mode_counts"]


def test_wrong_methods_on_collection_still_blocked():
    # the collection path stays read-only; only /{trade_id} accepts PATCH
    assert client.post("/api/operations/journal", json={}).status_code == 405
    assert client.delete("/api/operations/journal").status_code == 405
    assert client.patch("/api/operations/journal", json={"notes": "x"}).status_code in (404, 405)


def test_clearing_a_field_with_empty_string(trade_id):
    client.patch(f"/api/operations/journal/{trade_id}", json={"notes": "temp"})
    r = client.patch(f"/api/operations/journal/{trade_id}", json={"notes": ""})
    assert r.status_code == 200
    assert r.json()["entry"]["notes"] in (None, "")
