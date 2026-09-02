# -*- coding: utf-8 -*-
"""
Tests for Stage 11 — Operations Journal / Audit / System read-only adapter.

Confirms the adapter is a faithful, read-only pass-through of authoritative
SQLite state and `system_health.evaluate_system_health`, with the fail-closed
safety values intact and no execution / mutation surface.
"""
import database
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# --- Journal -----------------------------------------------------------
def test_journal_matches_closed_trades_table():
    r = client.get("/api/operations/journal")
    assert r.status_code == 200
    d = r.json()

    df = database.get_closed_trades()
    assert d["total_trades"] == len(df)
    assert d["writable"] is False
    assert d["source"] == "closed_trades"
    assert d["wins"] + d["losses"] <= d["total_trades"]
    if d["entries"]:
        e = d["entries"][0]
        assert {"trade_id", "symbol", "net_profit", "entry_time", "exit_time"} <= set(e)


def test_journal_is_read_only():
    assert client.post("/api/operations/journal", json={}).status_code == 405
    assert client.delete("/api/operations/journal").status_code == 405


# --- Audit -------------------------------------------------------------
def test_audit_matches_execution_orders_table():
    r = client.get("/api/operations/audit?limit=50")
    assert r.status_code == 200
    d = r.json()
    assert d["read_only"] is True
    assert d["source"] == "execution_orders"
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["total_returned"] <= 50
    assert d["total_returned"] <= d["total_records"]
    assert sum(d["state_counts"].values()) == d["total_records"]
    # signal_payload must never be exposed
    if d["events"]:
        assert "signal_payload" not in d["events"][0]
        # each row keeps its authoritative mode
        assert d["events"][0]["mode"] in (None, "PAPER", "SHADOW", "LIVE", "LIVE_MICRO")


def test_audit_limit_is_bounded():
    assert client.get("/api/operations/audit?limit=0").status_code == 422
    assert client.get("/api/operations/audit?limit=99999").status_code == 422


def test_audit_is_read_only():
    assert client.post("/api/operations/audit", json={}).status_code == 405
    assert client.delete("/api/operations/audit").status_code == 405
    assert client.get("/api/operations/audit/ack").status_code == 404


# --- System ----------------------------------------------------------
def test_system_preserves_failclosed_safety():
    r = client.get("/api/operations/system")
    assert r.status_code == 200
    d = r.json()
    assert d["live_automation_enabled"] is False
    assert d["live_broker_transmission"] == "BLOCKED"
    assert "safety_gate" in d
    gate = d["safety_gate"]
    assert set(("overall_status", "automation_allowed", "reasons")) <= set(gate)
    # health values agree with /api/health
    h = client.get("/api/health").json()
    assert d["version"] == h["version"]
    assert d["live_broker_transmission"] == h["live_broker_transmission"]


def test_system_has_no_toggle():
    assert client.post("/api/operations/system", json={}).status_code == 405
    assert client.post("/api/operations/system/enable", json={}).status_code == 404
