# -*- coding: utf-8 -*-
"""
Tests for Stage 3.5C — Risk Preview Latency Optimization
=======================================================
`POST /api/risk/preview` / `risk_gateway.calculate_pre_trade_risk_preview()`.

Verifies that reusing the Stage 3.5A 2s open-position cache and adding a bounded
300s correlation memo (preview path only) changes NOTHING about the risk math or
the correlation warnings, while eliminating repeated DB round trips:

1. Risk-output semantic parity (API vs authoritative engine), multiple instruments.
2. Correlation-warning parity: identical warnings with the memo on vs off.
3. Cache hit: a warm preview performs zero correlation / open-position DB work.
4. Cache expiry: correlation re-reads after its TTL elapses.
5. Open-position changes refresh within the 2s bound (no stale data past TTL).
6. The authoritative execution gate `evaluate_trade_risk()` still reads
   correlations UNCACHED (never served preview-cached values).
7. `RiskPreviewResponse` schema unchanged; fail-closed invariant intact.
"""
import time
import pytest
import pandas as pd
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.main import app
import database
import risk_gateway
from risk_gateway import calculate_pre_trade_risk_preview, get_pair_correlation

client = TestClient(app)

BASE_PAYLOAD = {
    "symbol": "XAUUSD",
    "side": "BUY",
    "entry_price": 2400.0,
    "stop_loss": 2390.0,
    "take_profit_1": 2420.0,
    "take_profit_2": 2440.0,
    "requested_risk_pct": 1.0,
    "account_balance": 10000.0,
}

RESPONSE_KEYS = {
    "symbol", "side", "entry_price", "stop_loss", "take_profit_1", "take_profit_2",
    "account_balance", "target_risk_usd", "calculated_lot_size", "actual_risk_usd",
    "actual_risk_pct", "reward_tp1_usd", "reward_tp1_pct", "reward_tp2_usd",
    "reward_tp2_pct", "risk_reward_ratio", "estimated_margin_usd", "is_valid",
    "warnings", "errors", "live_broker_transmission",
}

# Two correlated open positions vs an XAUUSD BUY preview.
_CORRELATED_POSITIONS = pd.DataFrame([
    {"position_id": "P1", "account_id": "PAPER", "symbol": "EURUSD", "direction": "BUY",
     "volume": 0.5, "entry_price": 1.08, "current_price": 1.081, "sl": 1.075, "tp": 1.09,
     "floating_pnl": 12.0},
    {"position_id": "P2", "account_id": "PAPER", "symbol": "GBPUSD", "direction": "SELL",
     "volume": 0.3, "entry_price": 1.27, "current_price": 1.269, "sl": 1.275, "tp": 1.26,
     "floating_pnl": 8.0},
])


@pytest.fixture(autouse=True)
def _reset_caches():
    """No global autouse reset exists in this repo — clear the preview caches per test."""
    risk_gateway.clear_correlation_cache()
    database.invalidate_db_cache("open_positions")
    yield
    risk_gateway.clear_correlation_cache()
    database.invalidate_db_cache("open_positions")


# ---------------------------------------------------------------------------
# 1. Risk-output semantic parity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("payload", [
    BASE_PAYLOAD,
    {"symbol": "EURUSD", "side": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800,
     "take_profit_1": 1.0950, "take_profit_2": 1.1000, "requested_risk_pct": 1.0,
     "account_balance": 10000.0},
    {"symbol": "USDJPY", "side": "SELL", "entry_price": 150.00, "stop_loss": 150.50,
     "take_profit_1": 149.00, "requested_risk_pct": 0.5, "account_balance": 25000.0},
    {"symbol": "BTCUSD", "side": "BUY", "entry_price": 60000.0, "stop_loss": 58000.0,
     "take_profit_1": 65000.0, "requested_risk_pct": 2.0, "account_balance": 50000.0},
    {"symbol": "NAS100", "side": "BUY", "entry_price": 20000.0, "stop_loss": 19800.0,
     "take_profit_1": 20500.0, "requested_risk_pct": 1.0, "account_balance": 15000.0},
])
def test_api_matches_engine_semantic_parity(payload):
    resp = client.post("/api/risk/preview", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    engine = calculate_pre_trade_risk_preview(
        symbol=payload["symbol"], side=payload["side"], entry_price=payload["entry_price"],
        stop_loss=payload["stop_loss"], take_profit_1=payload.get("take_profit_1"),
        take_profit_2=payload.get("take_profit_2"),
        requested_risk_pct=payload.get("requested_risk_pct", 1.0),
        account_balance=payload.get("account_balance", 10000.0),
    )

    for k in ("calculated_lot_size", "target_risk_usd", "actual_risk_usd", "actual_risk_pct",
              "reward_tp1_usd", "reward_tp1_pct", "reward_tp2_usd", "reward_tp2_pct",
              "estimated_margin_usd"):
        assert data[k] == pytest.approx(engine[k]), k
    assert data["risk_reward_ratio"] == engine["risk_reward_ratio"]
    assert data["is_valid"] == engine["is_valid"]
    assert data["errors"] == engine["errors"]
    assert data["warnings"] == engine["warnings"]
    assert data["live_broker_transmission"] == "BLOCKED"


def test_known_sizing_values_unchanged():
    """Locks the exact numbers from tests/test_smc_models.py::test_pre_trade_risk_preview."""
    preview = calculate_pre_trade_risk_preview(
        symbol="EURUSD", side="BUY", entry_price=1.0850, stop_loss=1.0800,
        take_profit_1=1.0950, take_profit_2=1.1000, requested_risk_pct=1.0,
        account_balance=10000.0,
    )
    assert preview["is_valid"] is True
    assert preview["calculated_lot_size"] == 0.20
    assert preview["actual_risk_usd"] == 100.0
    assert preview["actual_risk_pct"] == 1.0
    assert preview["reward_tp1_usd"] == 200.0


def test_invalid_geometry_still_flagged():
    bad = dict(BASE_PAYLOAD, stop_loss=2450.0)  # SL above entry for BUY
    resp = client.post("/api/risk/preview", json=bad)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is False
    assert len(data["errors"]) > 0


# ---------------------------------------------------------------------------
# 2. Correlation-warning parity: memo on vs off
# ---------------------------------------------------------------------------
def test_correlation_warnings_identical_with_and_without_memo(monkeypatch):
    monkeypatch.setattr(database, "get_open_positions",
                        lambda *a, **k: _CORRELATED_POSITIONS.copy())

    # Deterministic correlation values independent of DB contents.
    corr_table = {("EURUSD", "XAUUSD"): 0.88, ("GBPUSD", "XAUUSD"): -0.85}
    monkeypatch.setattr(risk_gateway, "_lookup_pair_correlation",
                        lambda a, b: corr_table.get(tuple(sorted((a, b))), 0.0))

    risk_gateway.clear_correlation_cache()
    uncached = calculate_pre_trade_risk_preview(**BASE_PAYLOAD)

    risk_gateway.clear_correlation_cache()
    first = calculate_pre_trade_risk_preview(**BASE_PAYLOAD)   # populates memo
    second = calculate_pre_trade_risk_preview(**BASE_PAYLOAD)  # served from memo

    assert uncached["warnings"] == first["warnings"] == second["warnings"]
    assert len(first["warnings"]) >= 1  # at least one correlated pair tripped >= 0.80


def test_get_pair_correlation_default_is_uncached_and_memo_matches():
    with patch.object(risk_gateway, "_lookup_pair_correlation", return_value=0.73) as look:
        # default ttl_sec=0.0 -> always delegates, never stores
        assert get_pair_correlation("XAUUSD", "EURUSD") == 0.73
        assert get_pair_correlation("XAUUSD", "EURUSD") == 0.73
        assert look.call_count == 2
        assert not risk_gateway._CORRELATION_CACHE

        # opt-in ttl -> one lookup, then served from memo, same value
        assert get_pair_correlation("XAUUSD", "EURUSD", ttl_sec=300.0) == 0.73
        assert get_pair_correlation("XAUUSD", "EURUSD", ttl_sec=300.0) == 0.73
        assert look.call_count == 3


# ---------------------------------------------------------------------------
# 3. Cache hit — warm preview does zero correlation / position DB work
# ---------------------------------------------------------------------------
def test_warm_preview_hits_no_database(monkeypatch):
    monkeypatch.setattr(database, "get_open_positions",
                        lambda *a, **k: _CORRELATED_POSITIONS.copy())
    monkeypatch.setattr(risk_gateway, "_lookup_pair_correlation",
                        lambda a, b: 0.9 if "EURUSD" in (a, b) else 0.0)

    warm = calculate_pre_trade_risk_preview(**BASE_PAYLOAD)

    # Now every correlation pair is memoised; a second call must not touch the lookup.
    with patch.object(risk_gateway, "_lookup_pair_correlation",
                      side_effect=AssertionError("correlation DB hit on warm preview")):
        again = calculate_pre_trade_risk_preview(**BASE_PAYLOAD)
    assert again["warnings"] == warm["warnings"]


def test_warm_preview_reuses_open_position_cache():
    """The endpoint shares database._DB_CACHE['open_positions_None'] with the positions route."""
    database.invalidate_db_cache("open_positions")
    database.get_open_positions(ttl_sec=2.0)  # same call/key the positions route uses -> warms it
    assert "open_positions_None" in database._DB_CACHE
    with patch("database.get_connection",
               side_effect=AssertionError("get_connection during cached preview window")):
        resp = client.post("/api/risk/preview", json=BASE_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["is_valid"] is True


# ---------------------------------------------------------------------------
# 4. Cache expiry — correlation re-reads after TTL
# ---------------------------------------------------------------------------
def test_correlation_memo_expires_after_ttl():
    calls = []

    def fake_lookup(a, b):
        calls.append((a, b))
        return 0.5

    with patch.object(risk_gateway, "_lookup_pair_correlation", side_effect=fake_lookup):
        base = 1_000_000.0
        with patch.object(risk_gateway.time, "time", return_value=base):
            assert get_pair_correlation("XAUUSD", "EURUSD", ttl_sec=300.0) == 0.5
        with patch.object(risk_gateway.time, "time", return_value=base + 299.0):
            get_pair_correlation("XAUUSD", "EURUSD", ttl_sec=300.0)
            assert len(calls) == 1  # still within TTL
        with patch.object(risk_gateway.time, "time", return_value=base + 301.0):
            get_pair_correlation("XAUUSD", "EURUSD", ttl_sec=300.0)
            assert len(calls) == 2  # TTL elapsed -> refreshed


# ---------------------------------------------------------------------------
# 5. Open-position changes refresh within the 2s bound
# ---------------------------------------------------------------------------
def test_open_position_change_refreshes_within_ttl(monkeypatch):
    state = {"df": pd.DataFrame(columns=list(_CORRELATED_POSITIONS.columns))}
    real_get = database.get_open_positions

    def fake_get(account_id=None, ttl_sec: float = 0.0):
        # emulate database._DB_CACHE TTL semantics around the mutable state
        key = f"open_positions_{account_id}"
        if ttl_sec > 0 and key in database._DB_CACHE:
            df, ts = database._DB_CACHE[key]
            if time.time() - ts < ttl_sec:
                return df.copy()
        df = state["df"].copy()
        if ttl_sec > 0:
            database._DB_CACHE[key] = (df, time.time())
        return df.copy()

    monkeypatch.setattr(database, "get_open_positions", fake_get)
    monkeypatch.setattr(risk_gateway, "_lookup_pair_correlation", lambda a, b: 0.95)

    p1 = calculate_pre_trade_risk_preview(**BASE_PAYLOAD)
    assert p1["warnings"] == []

    # A new correlated position appears + cache is invalidated (as save_open_positions does)
    state["df"] = _CORRELATED_POSITIONS.copy()
    database.invalidate_db_cache("open_positions")

    p2 = calculate_pre_trade_risk_preview(**BASE_PAYLOAD)
    assert len(p2["warnings"]) >= 1  # no stale empty-portfolio result served past invalidation


# ---------------------------------------------------------------------------
# 6. Execution gate is never served preview-cached correlations
# ---------------------------------------------------------------------------
def test_execution_gate_uses_uncached_correlation(monkeypatch):
    seen_ttls = []
    orig = risk_gateway._lookup_pair_correlation

    def spy(a, b):
        return orig(a, b)

    real_get_pair = risk_gateway.get_pair_correlation

    def wrapped(sym_a, sym_b, ttl_sec: float = 0.0):
        seen_ttls.append(ttl_sec)
        return real_get_pair(sym_a, sym_b, ttl_sec=ttl_sec)

    monkeypatch.setattr(database, "get_open_positions",
                        lambda *a, **k: _CORRELATED_POSITIONS.copy())
    monkeypatch.setattr(risk_gateway, "get_pair_correlation", wrapped)
    monkeypatch.setattr(database, "get_account_balances",
                        lambda *a, **k: {"PAPER": {"balance": 10000.0, "equity": 10000.0,
                                                   "floating_pnl": 0.0}})

    risk_gateway.evaluate_trade_risk({
        "symbol": "XAUUSD", "side": "BUY", "volume": 0.05, "entry_price": 2400.0,
        "stop_loss": 2390.0, "mode": "PAPER", "broker": "CAPITAL",
    })

    assert seen_ttls, "evaluate_trade_risk did not evaluate correlation"
    assert all(t == 0.0 for t in seen_ttls), f"execution gate used cached correlation: {seen_ttls}"


# ---------------------------------------------------------------------------
# 7. Schema unchanged + fail-closed invariant
# ---------------------------------------------------------------------------
def test_response_schema_unchanged():
    data = client.post("/api/risk/preview", json=BASE_PAYLOAD).json()
    assert set(data.keys()) == RESPONSE_KEYS
    assert data["live_broker_transmission"] == "BLOCKED"


def test_no_order_or_execution_capability_added():
    assert client.post("/api/risk/execute", json={}).status_code == 404
    assert client.get("/api/risk/preview").status_code == 405   # POST-only
