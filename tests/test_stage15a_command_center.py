# -*- coding: utf-8 -*-
"""
Tests for Stage 15A — Daily Command Center.

`GET /api/command-center/overview` is a read-only aggregate: each section is a
re-shaped slice of an already-authoritative source (analytics / positions /
alerts / intelligence / forward-evidence / research notes). Nothing is
recomputed, nothing is mutated, there is no execution / broker path.
"""
import types

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import analytics
import database
from api.main import app

client = TestClient(app)


# 1. response schema + registration -----------------------------------
def test_overview_schema():
    r = client.get("/api/command-center/overview")
    assert r.status_code == 200
    d = r.json()
    assert set((
        "as_of", "session", "safety", "daily_performance", "account_summary",
        "positions", "alerts", "market_context", "research_state",
        "research_notes", "watchlist_highlights", "sections_degraded",
    )) <= set(d)
    assert d["source"] == "command_center_aggregate"
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["session"]["current_session"]
    assert isinstance(d["sections_degraded"], list)


# 2. safety section reflects the fail-closed flags -------------------
def test_overview_safety_is_failclosed():
    d = client.get("/api/command-center/overview").json()
    assert d["safety"]["automation_enabled"] is False
    assert d["safety"]["live_broker_transmission"] == "BLOCKED"
    h = client.get("/api/health").json()
    assert d["safety"]["automation_enabled"] == h["automation_enabled"]


# 3. daily / account sections trace to the canonical analytics fn ----
def test_daily_and_account_trace_to_canonical():
    d = client.get("/api/command-center/overview").json()
    if "account_summary" in d["sections_degraded"]:
        pytest.skip("analytics source degraded in this environment")

    df = database.get_closed_trades()
    for col in ("entry_time", "exit_time"):
        df[col] = pd.to_datetime(df[col], format="mixed", utc=True).dt.tz_localize(None)
    all_m = analytics.calculate_performance_metrics(df.sort_values("exit_time"), 10000.0)
    acct = d["account_summary"]
    assert acct["all_time_net_pnl"] == all_m["total_net_pnl"]
    assert acct["all_time_trades"] == all_m["total_trades"]
    assert acct["all_time_win_rate"] == all_m["win_rate"]
    assert acct["profit_factor"] == all_m["profit_factor"]
    assert acct["max_drawdown_pct"] == all_m["max_drawdown_pct"]

    # today's slice
    if d["daily_performance"]:
        today = pd.Timestamp(pd.Timestamp(d["daily_performance"]["date"]).date())
        day_df = df[(df["exit_time"] >= today) & (df["exit_time"] < today + pd.Timedelta(days=1))]
        day_m = analytics.calculate_performance_metrics(day_df, 10000.0)
        assert d["daily_performance"]["net_pnl"] == day_m["total_net_pnl"]
        assert d["daily_performance"]["trades"] == day_m["total_trades"]


# 4. positions / alerts trace to their canonical sources ------------
def test_positions_section_traces_to_db():
    d = client.get("/api/command-center/overview").json()
    if "positions" in d["sections_degraded"] or not d["positions"]:
        pytest.skip("positions degraded")
    df = database.get_open_positions()
    assert d["positions"]["total_open"] == (0 if df is None or df.empty else len(df))


def test_alerts_section_traces_to_db():
    d = client.get("/api/command-center/overview").json()
    if "alerts" in d["sections_degraded"] or not d["alerts"]:
        pytest.skip("alerts degraded")
    df = database.get_all_price_alerts(limit=50)
    active = 0 if df is None or df.empty else int((df["status"].astype(str).str.upper() == "ACTIVE").sum())
    assert d["alerts"]["active"] == active


# 5. deterministic between calls (barring live market drift) --------
def test_overview_stable_structural_fields():
    a = client.get("/api/command-center/overview").json()
    b = client.get("/api/command-center/overview").json()
    assert a["account_summary"] == b["account_summary"]
    assert a["session"]["current_session"] == b["session"]["current_session"]
    assert a["safety"] == b["safety"]


# 6. degraded-section contract -----------------------------------
def test_degraded_section_is_named_not_fatal(monkeypatch):
    import api.routers.command_center as mod

    def boom():
        raise RuntimeError("simulated source failure")

    monkeypatch.setattr(mod, "_positions_section", boom)
    r = client.get("/api/command-center/overview")
    assert r.status_code == 200
    d = r.json()
    assert "positions" in d["sections_degraded"]
    assert d["positions"] is None
    # other sections still populated
    assert d["session"]["current_session"]


# 7-11. read-only / no execution side effects --------------------
def test_overview_is_get_only():
    assert client.post("/api/command-center/overview", json={}).status_code == 405
    assert client.put("/api/command-center/overview", json={}).status_code == 405
    assert client.delete("/api/command-center/overview").status_code == 405


def test_overview_does_not_touch_execution_state():
    sys_before = client.get("/api/operations/system").json()
    audit_before = client.get("/api/operations/audit?limit=1").json()

    for _ in range(3):
        client.get("/api/command-center/overview")

    sys_after = client.get("/api/operations/system").json()
    audit_after = client.get("/api/operations/audit?limit=1").json()
    h = client.get("/api/health").json()

    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"
    assert sys_before["open_positions"] == sys_after["open_positions"]
    assert audit_before["total_records"] == audit_after["total_records"]
    assert audit_before["mode_counts"] == audit_after["mode_counts"]


def test_command_center_router_binds_no_execution_symbol():
    import api.routers.command_center as mod
    forbidden = {"execution_pipeline", "broker_adapter", "risk_gateway",
                 "submit_order", "get_broker_adapter", "CanonicalExecutionRequest"}
    for name, value in vars(mod).items():
        assert name not in forbidden, f"binds {name}"
        if isinstance(value, types.ModuleType):
            assert value.__name__.split(".")[0] not in forbidden, f"imports {value.__name__}"
