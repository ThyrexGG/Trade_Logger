# -*- coding: utf-8 -*-
"""
Tests for Stage 14 — Analytics migration.

`GET /api/analytics/performance` is a read-only adapter over the authoritative
`analytics.calculate_performance_metrics` + the `closed_trades` table. It only
filters the population (account / symbol / date, exactly as the Streamlit
"ANALYTICS & OVERVIEW" tab) and shapes derived series. No formula is
reimplemented; no execution / broker / order path exists.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import analytics
import database
from api.main import app

client = TestClient(app)


def _canonical_metrics(account=None, symbols=None, start=None, end=None, initial_balance=10000.0):
    """Reproduce the exact filtered population + canonical metrics the Streamlit page uses."""
    df = database.get_closed_trades()
    if df.empty:
        return analytics.calculate_performance_metrics(pd.DataFrame(), initial_balance), 0
    for col in ("entry_time", "exit_time"):
        df[col] = pd.to_datetime(df[col], format="mixed", utc=True).dt.tz_localize(None)
    if account and account != "ALL":
        df = df[df["account_id"].astype(str) == account]
    if symbols:
        df = df[df["symbol"].astype(str).str.upper().isin([s.upper() for s in symbols])]
    if start:
        df = df[df["exit_time"] >= pd.Timestamp(start)]
    if end:
        df = df[df["exit_time"] < pd.Timestamp(end) + pd.Timedelta(days=1)]
    df = df.sort_values(by="exit_time").reset_index(drop=True)
    return analytics.calculate_performance_metrics(df, initial_balance), len(df)


# 1 & 2. response shape + authoritative source ---------------------------
def test_response_shape_and_source():
    d = client.get("/api/analytics/performance").json()
    assert set((
        "metrics", "equity_curve", "daily_pnl", "symbol_breakdown", "tag_breakdown",
        "period_returns", "available", "filters_applied", "matched_trades",
    )) <= set(d)
    assert d["source"] == "closed_trades"
    assert d["live_broker_transmission"] == "BLOCKED"
    mk = set(d["metrics"])
    assert {"total_trades", "win_rate", "profit_factor", "sqn", "expectancy",
            "max_drawdown_pct", "long_stats", "short_stats", "best_symbols"} <= mk


# 3 & 9. known dataset -> canonical metrics ----------------------------
def test_metrics_match_canonical_function():
    r = client.get("/api/analytics/performance")
    assert r.status_code == 200
    api_m = r.json()["metrics"]
    canon, n = _canonical_metrics()
    assert r.json()["matched_trades"] == n
    for k in ("total_trades", "winning_trades", "losing_trades", "win_rate",
              "total_net_pnl", "total_gross_profit", "total_gross_loss",
              "profit_factor", "expectancy", "max_drawdown_usd", "max_drawdown_pct",
              "sqn", "gain_pct", "final_balance", "peak_balance", "best_trade", "worst_trade"):
        assert api_m[k] == canon[k], f"{k}: api={api_m[k]} canon={canon[k]}"
    assert api_m["long_stats"] == canon["long_stats"]
    assert api_m["short_stats"] == canon["short_stats"]
    assert [s["symbol"] for s in api_m["best_symbols"]] == [s["symbol"] for s in canon["best_symbols"]]


# 4. empty dataset behavior ------------------------------------------
def test_empty_population_returns_zeroed_metrics():
    # a date window before any trade exist
    d = client.get("/api/analytics/performance?start=1990-01-01&end=1990-01-02").json()
    assert d["matched_trades"] == 0
    assert d["metrics"]["total_trades"] == 0
    assert d["metrics"]["total_net_pnl"] == 0.0
    assert d["equity_curve"] == []
    assert d["symbol_breakdown"] == []


# 5. date filtering -------------------------------------------------
def test_date_filter_narrows_population():
    full = client.get("/api/analytics/performance").json()
    dmin = full["available"]["date_min"]
    dmax = full["available"]["date_max"]
    narrowed = client.get(f"/api/analytics/performance?start={dmax}&end={dmax}").json()
    assert narrowed["matched_trades"] <= full["matched_trades"]
    _, n = _canonical_metrics(start=dmax, end=dmax)
    assert narrowed["matched_trades"] == n
    assert narrowed["filters_applied"]["start"] == dmax
    # a window equal to the whole range keeps everything
    whole = client.get(f"/api/analytics/performance?start={dmin}&end={dmax}").json()
    assert whole["matched_trades"] == full["matched_trades"]


# 6. symbol filtering ---------------------------------------------
def test_symbol_filter_matches_canonical():
    full = client.get("/api/analytics/performance").json()
    syms = full["available"]["symbols"]
    if not syms:
        pytest.skip("no trades to filter")
    one = syms[0]
    r = client.get(f"/api/analytics/performance?symbols={one}").json()
    _, n = _canonical_metrics(symbols=[one])
    assert r["matched_trades"] == n
    assert all(row["symbol"] == one for row in r["symbol_breakdown"])


def test_account_filter_matches_canonical():
    full = client.get("/api/analytics/performance").json()
    accts = full["available"]["accounts"]
    if not accts:
        pytest.skip("no trades")
    a = accts[0]
    r = client.get(f"/api/analytics/performance?account={a}").json()
    _, n = _canonical_metrics(account=a)
    assert r["matched_trades"] == n
    assert r["filters_applied"]["account"] == a


# 7. invalid filter handling -----------------------------------
@pytest.mark.parametrize("qs,code", [
    ("account=DOES_NOT_EXIST", 422),
    ("symbols=NOTASYMBOL", 422),
    ("start=2026/01/01", 422),
    ("end=garbage", 422),
    ("start=2026-06-01&end=2026-01-01", 422),
    ("initial_balance=0", 422),
    ("initial_balance=-100", 422),
])
def test_invalid_filters_rejected(qs, code):
    assert client.get(f"/api/analytics/performance?{qs}").status_code == code


# 8. deterministic / repeatable ---------------------------------
def test_deterministic_results():
    a = client.get("/api/analytics/performance").json()
    b = client.get("/api/analytics/performance").json()
    assert a["metrics"] == b["metrics"]
    assert a["equity_curve"] == b["equity_curve"]
    assert a["symbol_breakdown"] == b["symbol_breakdown"]
    assert a["matched_trades"] == b["matched_trades"]


# equity curve traceability -----------------------------------
def test_equity_curve_traces_to_trades():
    d = client.get("/api/analytics/performance?initial_balance=10000").json()
    if d["matched_trades"] < 2:
        pytest.skip("need trades")
    _, n = _canonical_metrics(initial_balance=10000)
    # last equity == starting balance + total net pnl
    last = d["equity_curve"][-1]["equity"]
    assert abs(last - (10000 + d["metrics"]["total_net_pnl"])) < 0.02


# 10-15. no execution / broker side effects -------------------
def test_analytics_is_get_only():
    assert client.post("/api/analytics/performance", json={}).status_code == 405
    assert client.delete("/api/analytics/performance").status_code == 405
    assert client.put("/api/analytics/performance", json={}).status_code == 405


def test_analytics_does_not_touch_execution_state():
    sys_before = client.get("/api/operations/system").json()
    audit_before = client.get("/api/operations/audit?limit=1").json()

    for qs in ("", "?account=ALL", "?symbols=" + ",".join(client.get("/api/analytics/performance").json()["available"]["symbols"][:1])):
        client.get(f"/api/analytics/performance{qs}")

    sys_after = client.get("/api/operations/system").json()
    audit_after = client.get("/api/operations/audit?limit=1").json()
    h = client.get("/api/health").json()

    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"
    assert sys_after["live_automation_enabled"] is False
    assert sys_before["open_positions"] == sys_after["open_positions"]
    assert audit_before["total_records"] == audit_after["total_records"]
    assert audit_before["mode_counts"] == audit_after["mode_counts"]


def test_analytics_router_binds_no_execution_symbol():
    import types
    import api.routers.analytics as mod
    forbidden = {"execution_pipeline", "broker_adapter", "risk_gateway", "submit_order",
                 "get_broker_adapter", "research_analytics"}
    for name, value in vars(mod).items():
        assert name not in forbidden
        if isinstance(value, types.ModuleType):
            assert value.__name__.split(".")[0] not in forbidden


def test_existing_analytics_module_unchanged_contract():
    """The migration must not have weakened the canonical function."""
    empty = analytics.calculate_performance_metrics(pd.DataFrame(), 10000.0)
    assert empty["total_trades"] == 0 and empty["profit_factor"] == 1.0
    assert set(empty) >= {"win_rate", "sqn", "expectancy", "max_drawdown_pct", "long_stats"}
