# -*- coding: utf-8 -*-
"""
Tests for Stage 15B — Research Lab / adversarial audit migration.

`POST /api/research/audit` runs one authoritative `backtester.run_backtest`
then applies the canonical `research_analytics.*` + `research_engine.*`
functions to its trades. No formula is reimplemented. Research-only: no
execution / broker / automation path.
"""
import types

import pytest
from fastapi.testclient import TestClient

import backtester
import research_analytics
import research_engine
from api.main import app

client = TestClient(app)

BASE = {"symbol": "XAUUSD", "timeframe": "1h", "strategy": "Trend Continuation"}


# --- validation --------------------------------------------------------
@pytest.mark.parametrize("body,code", [
    ({**BASE, "timeframe": "3h"}, 422),
    ({**BASE, "strategy": "Does Not Exist"}, 422),
    ({**BASE, "symbol": "NOTREAL"}, 422),
    ({**BASE, "capital": -1}, 422),
    ({**BASE, "train_split": 0.95}, 422),
    ({**BASE, "train_split": 0.05}, 422),
])
def test_audit_rejects_invalid_config(body, code):
    assert client.post("/api/research/audit", json=body).status_code == code


def test_audit_is_post_only():
    assert client.get("/api/research/audit").status_code == 405
    assert client.delete("/api/research/audit").status_code == 405
    assert client.put("/api/research/audit", json=BASE).status_code == 405


# --- a full run + canonical parity -----------------------------------
@pytest.fixture(scope="module")
def audit_result():
    r = client.post("/api/research/audit", json=BASE)
    assert r.status_code == 200, r.text
    return r.json()


def test_audit_response_shape(audit_result):
    d = audit_result
    assert d["status"] in ("complete", "failed")
    if d["status"] == "failed":
        pytest.skip(f"backtest produced too few trades in this env: {d.get('error')}")
    assert set((
        "layer_expectancy", "bootstrap_ci", "scorecard", "execution_stress",
        "expectancy_drift", "liquidity_breakdown", "session_breakdown",
        "confluence", "sample_n", "contract_hash",
    )) <= set(d)
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["scorecard"]["status"] in (
        "STRONG", "PROMISING", "UNCERTAIN", "FAILED", "INSUFFICIENT DATA",
    )


def test_audit_metrics_match_canonical_functions(audit_result):
    d = audit_result
    if d["status"] != "complete":
        pytest.skip("no complete run")

    # Reproduce the exact pipeline the router runs (same seed, same splits).
    res = backtester.run_backtest(
        symbol="XAUUSD", timeframe="1h", strategy="Trend Continuation",
        risk_pct=1.0, sl_atr=1.5, tp_atr=2.0, capital=10000.0,
        slippage=0.0001, commission_pct=0.01, fixed_spread=0.0, train_split=0.60,
    )
    raw_trades = res.get("trades") or []
    df_r = research_analytics.calculate_trade_r_multiples(raw_trades)
    n = len(df_r)
    assert d["sample_n"] == n

    oos = df_r.iloc[int(n * 0.60):]
    boot = research_engine.BootstrapEstimator.calculate_r_expectancy_ci(
        list(oos["r_multiple"].values), n_iterations=3000, random_seed=42,
    )
    assert d["bootstrap_ci"]["ci_lower"] == boot["ci_lower"]
    assert d["bootstrap_ci"]["ci_upper"] == boot["ci_upper"]
    assert d["bootstrap_ci"]["verdict"] == boot["verdict"]

    hold = df_r.iloc[int(n * 0.80):]
    assert d["layer_expectancy"]["holdout_r"] == round(float(hold["r_multiple"].mean()), 3)

    stress = research_analytics.stress_test_execution_sensitivity(raw_trades)
    assert d["execution_stress"]["fragility_rating"] == stress["fragility_rating"]
    assert len(d["execution_stress"]["scenarios"]) == len(stress["scenarios"])


def test_audit_deterministic(audit_result):
    if audit_result["status"] != "complete":
        pytest.skip("no complete run")
    again = client.post("/api/research/audit", json=BASE).json()
    assert again["bootstrap_ci"] == audit_result["bootstrap_ci"]
    assert again["layer_expectancy"] == audit_result["layer_expectancy"]
    assert again["scorecard"]["status"] == audit_result["scorecard"]["status"]
    assert again["sample_n"] == audit_result["sample_n"]


def test_too_few_trades_is_a_clean_failure():
    # 5m XAUUSD over 60d frequently yields very few strategy trades; the endpoint
    # must return a structured failure, never 500.
    r = client.post("/api/research/audit", json={**BASE, "timeframe": "5m", "train_split": 0.6})
    assert r.status_code == 200
    assert r.json()["status"] in ("complete", "failed")


# --- safety -----------------------------------------------------------
def test_audit_does_not_touch_execution_state(audit_result):
    sys_before = client.get("/api/operations/system").json()
    audit_before = client.get("/api/operations/audit?limit=1").json()

    client.post("/api/research/audit", json=BASE)

    sys_after = client.get("/api/operations/system").json()
    audit_after = client.get("/api/operations/audit?limit=1").json()
    h = client.get("/api/health").json()

    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"
    assert sys_before["open_positions"] == sys_after["open_positions"]
    assert audit_before["total_records"] == audit_after["total_records"]
    assert audit_before["mode_counts"] == audit_after["mode_counts"]


def test_research_router_binds_no_execution_symbol():
    import api.routers.research as mod
    forbidden = {"execution_pipeline", "broker_adapter", "risk_gateway",
                 "submit_order", "get_broker_adapter", "CanonicalExecutionRequest"}
    for name, value in vars(mod).items():
        assert name not in forbidden, f"binds {name}"
        if isinstance(value, types.ModuleType):
            assert value.__name__.split(".")[0] not in forbidden, f"imports {value.__name__}"


def test_existing_research_analytics_contract_intact():
    """The migration must not have weakened the canonical research functions."""
    trades = [
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0950},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0800},
        {"direction": "SELL", "entry_price": 1.0850, "stop_loss": 1.0900, "exit_price": 1.0700},
    ]
    df = research_analytics.calculate_trade_r_multiples(trades)
    assert list(df["r_multiple"]) == [2.0, -1.0, 3.0]
    stress = research_analytics.stress_test_execution_sensitivity(trades)
    assert "fragility_rating" in stress and len(stress["scenarios"]) > 1
