# -*- coding: utf-8 -*-
"""
Tests for Stage 10 — Strategy Lab & Backtesting research adapter.

Covers the read-only strategy surface and the request-validation / safety
contract of the backtest endpoint. A full `run_backtest` is intentionally NOT
exercised here (it fetches live market data and takes several seconds); the
authoritative engine keeps its own coverage in `test_backtester.py`.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
import backtester
import strategies
from xauusd_market_conditions import FROZEN_CONTRACT_HASH

client = TestClient(app)


# --- GET /api/research/strategy -------------------------------------------
def test_strategy_lab_surface_is_authoritative():
    r = client.get("/api/research/strategy")
    assert r.status_code == 200
    d = r.json()

    assert d["contract_hash"] == FROZEN_CONTRACT_HASH
    assert d["mode"] == "RESEARCH"
    assert d["live_broker_transmission"] == "BLOCKED"

    # strategies come straight from the registry
    reg_names = set(strategies.STRATEGY_REGISTRY)
    assert {s["name"] for s in d["strategies"]} == reg_names
    assert len(d["strategies"]) >= 1

    # every advertised symbol really maps to a data feed
    for sym in d["supported_symbols"]:
        assert backtester.map_symbol_to_yf(sym), sym

    # timeframe mapping matches the backtester source
    tfs = {t["timeframe"] for t in d["timeframes"]}
    assert tfs == {"1h", "1d", "15m", "5m"}

    assert d["methodology"]["lookahead_protection"] is True


def test_strategy_lab_defaults_match_engine_signatures():
    d = client.get("/api/research/strategy").json()
    import inspect

    sig = inspect.signature(backtester.run_backtest)
    assert d["backtest_defaults"]["risk_pct"] == sig.parameters["risk_pct"].default
    assert d["backtest_defaults"]["capital"] == sig.parameters["capital"].default

    import research_engine
    import dataclasses

    re_defaults = {
        f.name: f.default for f in dataclasses.fields(research_engine.ResearchExperiment)
    }
    assert d["research_defaults"]["random_seed"] == re_defaults["random_seed"]
    assert d["research_defaults"]["train_split"] == re_defaults["train_split"]


# --- POST /api/research/backtest — validation & safety -------------------
def test_backtest_rejects_unknown_strategy():
    r = client.post("/api/research/backtest", json={"strategy": "Does Not Exist"})
    assert r.status_code == 422


def test_backtest_rejects_unknown_symbol():
    r = client.post("/api/research/backtest", json={"symbol": "NOTASYMBOL"})
    assert r.status_code == 422


def test_backtest_rejects_bad_timeframe_mode_split():
    assert client.post("/api/research/backtest", json={"timeframe": "3m"}).status_code == 422
    assert client.post("/api/research/backtest", json={"mode": "live"}).status_code == 422
    assert client.post("/api/research/backtest", json={"train_split": 2.0}).status_code == 422
    assert client.post("/api/research/backtest", json={"capital": 0}).status_code == 422


def test_backtest_has_no_execution_surface():
    # no GET, no execute/order variants
    assert client.get("/api/research/backtest").status_code == 405
    assert client.post("/api/research/execute", json={}).status_code == 404
    assert client.post("/api/research/order", json={}).status_code == 404


@pytest.mark.parametrize("path", ["/api/research/strategy"])
def test_get_is_read_only(path):
    # a GET must never mutate — repeated calls are identical
    a = client.get(path).json()
    b = client.get(path).json()
    a.pop("timestamp", None)
    b.pop("timestamp", None)
    assert a == b
