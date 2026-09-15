# -*- coding: utf-8 -*-
"""
Tests for W15 — the killzone liquidity-sweep + MSS scanner
(`killzone_scanner.py`, `api/routers/scanner.py`).

Pattern-flagging only: no execution path, no order/broker import, no win-
probability or recommendation computed anywhere in this module. Detection
correctness is tested against a hand-built synthetic candle series with a
known, deliberately engineered sweep + structure-shift in it — not live
market data, which is what the router-level tests exercise instead (network-
tolerant: skipped rather than failed if the upstream feed is unreachable).
"""
import math
import types

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import killzone_scanner as ks
import market_data
from api.main import app

client = TestClient(app)


def _build_series() -> pd.DataFrame:
    """A gently oscillating base (clean, confirmable swing points) followed by
    a deliberate sell-side liquidity sweep and a bullish structure shift a few
    candles later — the exact ICT-style event the scanner exists to flag."""
    rows = []
    t = 1_700_000_000
    price = 100.0
    for i in range(40):
        o = price
        wobble = math.sin(i / 3.0) * 0.5
        h = o + 0.2 + max(0.0, wobble)
        l = o - 0.2 - max(0.0, -wobble)
        c = o + wobble * 0.3
        rows.append({"time": t, "open": round(o, 4), "high": round(h, 4), "low": round(l, 4), "close": round(c, 4), "volume": 100})
        price = c
        t += 900

    price = rows[-1]["close"]
    for _ in range(3):
        o, h, l, c = price, price + 0.15, price - 0.15, price - 0.05
        rows.append({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 100})
        t += 900
        price = c

    # sweep: wick below the ~99.636 swing low, close back above it
    o, l, h, c = price, 99.60, price + 0.1, 99.70
    rows.append({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 100})
    sweep_time = t
    t += 900
    price = c

    o, h, l, c = price, price + 0.1, price - 0.1, price + 0.05
    rows.append({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 100})
    t += 900
    price = c

    # shift: strong bullish displacement closing above the ~101.26 swing high
    o, c = price, 101.6
    h, l = c + 0.05, o - 0.05
    rows.append({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 100})
    shift_time = t
    t += 900
    price = c

    for _ in range(3):
        o, h, l, c = price, price + 0.15, price - 0.15, price + 0.05
        rows.append({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 100})
        t += 900
        price = c

    df = pd.DataFrame(rows)
    return df, sweep_time, shift_time


# --- detection correctness (synthetic, deterministic) ----------------------

def test_detects_the_engineered_sweep():
    df, sweep_time, _ = _build_series()
    sweeps = ks.detect_liquidity_sweeps(df)
    matches = [s for s in sweeps if s["time"] == sweep_time]
    assert len(matches) == 1
    assert matches[0]["type"] == "SSL_SWEEP"
    assert matches[0]["wick_price"] < matches[0]["level"] < matches[0]["close_price"]


def test_detects_the_engineered_shift():
    df, _, shift_time = _build_series()
    shifts = ks.detect_structure_shifts(df)
    matches = [s for s in shifts if s["time"] == shift_time]
    assert len(matches) == 1
    assert matches[0]["direction"] == "bullish"


def test_pairs_sweep_and_shift_into_one_candidate():
    df, sweep_time, shift_time = _build_series()
    candidates = ks.find_candidates(df)
    assert len(candidates) == 1
    c = candidates[0]
    assert c["direction"] == "bullish"
    assert c["sweep_time"] == sweep_time
    assert c["shift_time"] == shift_time


def test_a_shift_with_no_prior_opposing_sweep_is_not_a_candidate():
    # a pure uptrend with no sweep at all should never produce a candidate,
    # even though it clears swing highs (that's a BOS, not a swept-liquidity MSS)
    rows = []
    t = 1_700_000_000
    price = 100.0
    for i in range(30):
        c = price + 0.05
        rows.append({"time": t, "open": price, "high": c + 0.05, "low": price - 0.05, "close": c, "volume": 100})
        price = c
        t += 900
    df = pd.DataFrame(rows)
    assert ks.find_candidates(df) == []


def test_empty_and_undersized_data_returns_no_detections():
    empty = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    assert ks.detect_liquidity_sweeps(empty) == []
    assert ks.detect_structure_shifts(empty) == []
    tiny = pd.DataFrame([{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}])
    assert ks.detect_liquidity_sweeps(tiny) == []


# --- scan() orchestration (mocked data source, deterministic) -------------

def test_scan_reports_htf_bias_and_agreement(monkeypatch):
    ltf_df, _, _ = _build_series()
    htf_rows = ltf_df.to_dict("records")  # reuse the same shape as a stand-in HTF series

    def fake_candles(symbol, timeframe, count, ttl_sec=0):
        rows = ltf_df.to_dict("records") if timeframe == "15m" else htf_rows
        return rows, "yahoo"

    monkeypatch.setattr(market_data, "get_candles_with_source", fake_candles)
    result = ks.scan("USDJPY", ltf="15m", htf="1h")
    assert result["ok"] is True
    assert result["symbol"] == "USDJPY"
    assert result["htf_bias"] in ("bullish", "bearish", "neutral")
    assert len(result["candidates"]) == 1
    assert "agrees_with_htf_bias" in result["candidates"][0]
    assert "not a signal" in result["disclaimer"].lower()


def test_scan_handles_empty_data_gracefully(monkeypatch):
    monkeypatch.setattr(market_data, "get_candles_with_source", lambda *a, **k: ([], "unknown"))
    result = ks.scan("USDJPY")
    assert result["ok"] is False
    assert "error" in result and result["error"]


def test_scan_never_raises_on_a_data_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("upstream feed exploded")
    monkeypatch.setattr(market_data, "get_candles_with_source", boom)
    result = ks.scan("USDJPY")
    assert result["ok"] is False
    assert "error" in result


# --- router -----------------------------------------------------------------

def test_killzone_route_is_get_only():
    assert client.post("/api/scanner/killzone").status_code == 405


def test_killzone_route_never_500s_even_on_upstream_failure(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr("killzone_scanner.market_data.get_candles_with_source", boom)
    r = client.get("/api/scanner/killzone?symbol=USDJPY")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False
    assert d["live_broker_transmission"] == "BLOCKED"


def test_killzone_route_against_real_data_or_skip():
    """Best-effort live check — skipped, not failed, if the upstream feed is
    unreachable from this environment (network policy, rate limit, etc.)."""
    r = client.get("/api/scanner/killzone?symbol=USDJPY")
    assert r.status_code == 200
    d = r.json()
    if not d["ok"]:
        pytest.skip(f"live data unavailable in this environment: {d.get('error')}")
    assert d["symbol"] == "USDJPY"
    assert d["htf_bias"] in ("bullish", "bearish", "neutral")
    assert isinstance(d["candidates"], list)


# --- execution isolation ----------------------------------------------------

def test_scanner_binds_no_execution_symbol():
    import api.routers.scanner as router_mod

    forbidden_names = {
        "execution_pipeline", "broker_adapter", "risk_gateway", "submit_order",
        "get_broker_adapter", "CanonicalExecutionRequest", "execution_recorder",
    }
    for mod in (ks, router_mod):
        for name, value in vars(mod).items():
            assert name not in forbidden_names, f"{mod.__name__} binds {name}"
            if isinstance(value, types.ModuleType):
                top = value.__name__.split(".")[0]
                assert top not in forbidden_names, f"{mod.__name__} imports {value.__name__}"
