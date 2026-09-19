# -*- coding: utf-8 -*-
"""
The phone app reads the API through hand-copied TypeScript types
(mobile/src/types/*.ts). This drives every endpoint the Phase-2 screens use
against a throwaway sqlite database and checks that each field the phone
declares as required is actually in the response — so a backend rename or a
typo in a phone type shows up here, not on someone's phone.

Never touches the developer's real database (see [[local-env-points-at-production-db]]).
"""
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import database
import tenant
from api.main import app

client = TestClient(app)
TYPES = Path(__file__).resolve().parent.parent / "mobile" / "src" / "types"


def required_fields(file: str, interface: str) -> set:
    """Required (non-optional) property names of `export interface <interface>` in a phone type file."""
    text = (TYPES / file).read_text(encoding="utf-8")
    m = re.search(r"export interface " + re.escape(interface) + r"\b[^{]*\{(.*?)\n\}", text, re.S)
    assert m, f"{interface} not found in {file}"
    out = set()
    depth = 0  # only top-level properties count, not the fields of an inline `{ ... }` object type
    for line in m.group(1).splitlines():
        stripped = line.strip()
        fm = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(\??):", stripped)
        if depth == 0 and fm and not fm.group(2):
            out.add(fm.group(1))
        depth += stripped.count("{") - stripped.count("}")
    return out


def assert_has(payload: dict, file: str, interface: str):
    missing = required_fields(file, interface) - set(payload.keys())
    assert not missing, f"{interface}: the phone reads {sorted(missing)} but the API did not send it"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "contract.db")
    monkeypatch.setattr(database, "get_db_url", lambda: None)
    monkeypatch.setattr(database, "get_connection", lambda: sqlite3.connect(path, timeout=30))
    monkeypatch.setattr(database, "_PUSH_TABLES_READY", False)
    monkeypatch.setattr(database, "_DB_INITIALIZED", False)
    database.init_db(force=True)
    database.invalidate_db_cache()
    with tenant.use("phone-contract"):
        yield path


def _iso(delta):
    return (datetime.now(timezone.utc) + delta).isoformat()


def _manual(account="OWN_MONEY", symbol="EURUSD", gross=42.5, days_ago=1, tag="BREAKOUT"):
    body = {
        "account_id": account, "symbol": symbol, "direction": "BUY", "volume": 0.5,
        "entry_price": 1.08, "exit_price": 1.09, "commission": -1.0, "swap": 0.0,
        "gross_profit": gross,
        "entry_time": _iso(timedelta(days=-days_ago, hours=-2)),
        "exit_time": _iso(timedelta(days=-days_ago)),
        "setup_tag": tag, "notes": "contract test",
    }
    r = client.post("/api/operations/journal/trades", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_manual_trade_response_matches_phone_journal_type(db):
    trade = _manual()
    assert_has(trade, "journal.ts", "JournalTradeItem")
    assert trade["trade_id"].startswith("MANUAL_")
    assert trade["net_profit"] == pytest.approx(41.5)


def test_manual_trade_rejects_exit_before_entry(db):
    body = {
        "account_id": "A", "symbol": "EURUSD", "direction": "BUY", "gross_profit": 1.0,
        "entry_time": _iso(timedelta(hours=-1)), "exit_time": _iso(timedelta(hours=-3)),
    }
    assert client.post("/api/operations/journal/trades", json=body).status_code == 422


def test_analytics_performance_and_day_match_phone_types(db):
    t1 = _manual(gross=100, days_ago=2)
    _manual(gross=-30, days_ago=1, symbol="GBPUSD", tag="NEWS SCALP")

    r = client.get("/api/analytics/performance", params={"account": "OWN_MONEY", "initial_balance": 350})
    assert r.status_code == 200, r.text
    d = r.json()
    assert_has(d, "analytics.ts", "AnalyticsPerformanceResponse")
    assert_has(d["metrics"], "analytics.ts", "PerformanceMetrics")
    assert_has(d["metrics"]["long_stats"], "analytics.ts", "DirectionStats")
    assert_has(d["period_returns"], "analytics.ts", "PeriodReturns")
    assert_has(d["filters_applied"], "analytics.ts", "AnalyticsFiltersEcho")
    assert_has(d["available"], "analytics.ts", "AnalyticsAvailable")
    for row in d["equity_curve"]:
        assert_has(row, "analytics.ts", "EquityAnchor")
    for row in d["daily_pnl"]:
        assert_has(row, "analytics.ts", "DailyPnl")
    for row in d["symbol_breakdown"]:
        assert_has(row, "analytics.ts", "SymbolBreakdownRow")
    for row in d["tag_breakdown"]:
        assert_has(row, "analytics.ts", "TagBreakdownRow")
    assert d["matched_trades"] == 2
    assert d["metrics"]["total_net_pnl"] == pytest.approx(68.0)   # (100-1) + (-30-1)
    assert d["available"]["accounts"] == ["OWN_MONEY"]

    day = d["daily_pnl"][0]["date"]
    r2 = client.get("/api/analytics/day", params={"date": day, "account": "OWN_MONEY"})
    assert r2.status_code == 200, r2.text
    dd = r2.json()
    assert_has(dd, "analytics.ts", "AnalyticsDayTradesResponse")
    assert dd["count"] >= 1
    for t in dd["trades"]:
        assert_has(t, "analytics.ts", "DayTrade")
    assert t1["trade_id"] in {t["trade_id"] for d_ in d["daily_pnl"] for t in client.get(
        "/api/analytics/day", params={"date": d_["date"], "account": "OWN_MONEY"}).json()["trades"]}


def test_starting_balance_round_trips_per_account(db):
    _manual()
    r = client.post("/api/analytics/initial-balance", params={"account": "OWN_MONEY", "value": 350})
    assert r.status_code == 200
    d = client.get("/api/analytics/performance", params={"account": "OWN_MONEY"}).json()
    assert d["available"]["saved_initial_balance"] == 350
    other = client.get("/api/analytics/performance").json()   # "all accounts" cannot hold one
    assert other["available"]["saved_initial_balance"] is None


def test_price_alert_crud_matches_phone_type(db):
    r = client.post("/api/alerts", json={"symbol": "xauusd", "target_price": 2400.5, "condition": "ABOVE", "notes": "n"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert_has(body["alert"], "alerts.ts", "AlertItem")
    aid = body["alert"]["id"]

    lst = client.get("/api/alerts").json()
    assert_has(lst, "alerts.ts", "AlertsResponse")
    assert lst["active"] == 1 and "XAUUSD" in lst["supported_symbols"]

    bad = client.post("/api/alerts", json={"symbol": "NOT_A_SYMBOL", "target_price": 1, "condition": "ABOVE"})
    assert bad.status_code == 422 and "Unsupported symbol" in bad.json()["detail"]

    assert client.delete(f"/api/alerts/{aid}").json()["deleted"] is True
    assert client.get("/api/alerts").json()["total"] == 0


def test_risk_preview_matches_phone_type(db):
    r = client.post("/api/risk/preview", json={
        "symbol": "EURUSD", "side": "BUY", "entry_price": 1.0800, "stop_loss": 1.0750,
        "take_profit_1": 1.0900, "take_profit_2": None, "requested_risk_pct": 1.0, "account_balance": 10000,
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert_has(d, "risk.ts", "RiskPreviewResponse")
    assert d["is_valid"] is True and d["calculated_lot_size"] > 0
    assert isinstance(d["warnings"], list) and isinstance(d["errors"], list)


def test_ai_status_matches_phone_type(db):
    d = client.get("/api/ai/status").json()
    assert_has(d, "ai.ts", "AIStatusResponse")


def test_journal_entry_prefill_shape_is_accepted(db):
    """'Plan this' on the Killzone screen creates a note with these exact fields."""
    r = client.post("/api/operations/journal/entries", json={
        "kind": "plan", "instrument": "USDJPY", "title": "USDJPY bullish plan",
        "body": "line one\nline two", "tags": ["killzone"],
    })
    assert r.status_code in (200, 201), r.text
    assert_has(r.json(), "entries.ts", "JournalEntry")


def test_killzone_types_declare_only_fields_the_backend_schema_has():
    """Cheap static check: every required field the phone declares exists on the backend model."""
    from api.schemas import KillzoneCandidate, KillzoneScanResponse
    for iface, model in (("KillzoneCandidate", KillzoneCandidate), ("KillzoneScanResponse", KillzoneScanResponse)):
        missing = required_fields("scanner.ts", iface) - set(model.model_fields)
        assert not missing, f"{iface}: {sorted(missing)} not on the backend model"
