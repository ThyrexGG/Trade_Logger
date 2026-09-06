# -*- coding: utf-8 -*-
"""
Phase 100 -- intraday setup co-pilot.

Covers: the named condition functions (pure, causal), the scan output
(conditions never rendered as BUY/SELL), the base-rate forward-outcome
engine and its verdict thresholds, reward:risk feasibility math, the
setup journal (log -> outcome -> realized R sign/magnitude) and the skill
tracker verdicts, evaluate_setup structure, determinism, persistence, the
read-only API surface, and safety invariants. The slow remote bar store
is fully monkeypatched; the real cache build is
``python -m phase100_intraday_copilot --refresh``.
"""
import inspect
import re

import numpy as np
import pandas as pd
import pytest

import phase100_intraday_copilot as cp


# --------------------------------------------------------------------------
def _augmented_frame(n=1200, seed=0, inject=None):
    """A synthetic frame with the columns phase76.load_bars produces."""
    rng = np.random.default_rng(seed)
    t0 = 1_700_000_000
    close = 100.0 + np.cumsum(rng.normal(0, 0.05, n))
    high = close + np.abs(rng.normal(0, 0.08, n))
    low = close - np.abs(rng.normal(0, 0.08, n))
    open_ = close - rng.normal(0, 0.03, n)
    if inject:
        inject(close, high, low, open_)
    ts = pd.to_datetime(t0 + np.arange(n) * 900, unit="s", utc=True)
    ret = np.concatenate([[0.0], np.diff(np.log(close))])
    prev_c = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_c), np.abs(low - prev_c)])
    atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
    df = pd.DataFrame({
        "t": t0 + np.arange(n) * 900, "open": open_, "high": high, "low": low, "close": close,
        "vol": 100.0, "hour": ts.hour, "minute": ts.minute, "year": ts.year, "date": ts.date,
        "ret": ret, "tr": tr, "atr": atr, "atr_ret": atr / close,
        "atr_ret_stable": pd.Series(atr / close).rolling(200, min_periods=50).mean().to_numpy(),
        "atr_rank": 0.5, "tr_atr": tr / np.where(atr > 0, atr, np.nan), "eff": 0.25,
        "regime": np.where(pd.Series(ret).rolling(20).sum().to_numpy() > 0, "TRENDING", "RANGING"),
        "session": np.select([ts.hour < 7, ts.hour < 12, ts.hour < 16, ts.hour < 21],
                             ["TOKYO", "LONDON", "LONDON_NY_OVERLAP", "NEW_YORK"], "LATE_US"),
    })
    daily = df.groupby("date").agg(dh=("high", "max"), dl=("low", "min"), dc=("close", "last"))
    daily["pdh"] = daily["dh"].shift(1); daily["pdl"] = daily["dl"].shift(1); daily["pdc"] = daily["dc"].shift(1)
    return df.merge(daily[["pdh", "pdl", "pdc"]], on="date", how="left")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    cp._BARS_CACHE.clear()
    monkeypatch.setattr(cp, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(cp.p76, "load_bars", lambda inst, tf: _augmented_frame(seed=hash((inst, tf)) % 999))
    monkeypatch.setattr(cp, "_raw_cache",
                        lambda inst, tf, refresh=False, allow_fetch=True: [{"time": 1}])  # non-empty
    store = {}
    monkeypatch.setattr(cp.store, "save_artifact", lambda k, kind, payload: store.__setitem__(k, payload) or "h")
    monkeypatch.setattr(cp.store, "load_artifact", lambda k: {"payload": store[k]} if k in store else None)
    monkeypatch.setattr(cp, "_macro_context", lambda: {"state": "UNAVAILABLE", "summary": "n/a"})
    return store


# --- A. conditions -----------------------------------------------------
def test_conditions_return_bool_arrays_aligned():
    df = _augmented_frame()
    for name, fn in cp.CONDITIONS.items():
        out = np.asarray(fn(df))
        assert out.dtype == bool and out.shape == (len(df),), name


def test_sweep_low_detects_pierce_and_reclaim():
    def inject(close, high, low, open_):
        low[600] = low[:600].min() - 5.0     # pierce well below
        close[600] = close[599] + 0.2        # but close back up
    df = _augmented_frame(inject=inject)
    assert bool(cp._cond_sweep_low(df)[600])


def test_inside_bar_flags_contained_range():
    def inject(close, high, low, open_):
        # force bar 500's range strictly inside bar 499's, and bar 501 strictly outside
        high[500] = min(high[499], high[500]) - 0.001
        low[500] = max(low[499], low[500]) + 0.001
        high[501] = high[500] + 5.0
    df = _augmented_frame(inject=inject)
    assert bool(cp._cond_inside_bar(df)[500])
    assert not bool(cp._cond_inside_bar(df)[501])


def test_conditions_are_causal():
    df = _augmented_frame(seed=3)
    m1 = cp._cond_range_extreme_high(df)
    df2 = df.copy()
    df2.loc[df2.index[-1], ["high", "close"]] += 50.0     # perturb only the last bar
    m2 = cp._cond_range_extreme_high(df2)
    assert np.array_equal(np.nan_to_num(m1[:-1]), np.nan_to_num(m2[:-1]))


# --- B. scan ----------------------------------------------------------
def test_scan_reports_conditions_not_signals():
    sc = cp.scan("EURUSD", "15m")
    assert sc["state"] == "OK"
    assert isinstance(sc["active_conditions"], list)
    blob = str(sc).upper()
    for banned in ("BUY", "SELL", "GO LONG", "GO SHORT", "ENTER NOW", "TAKE THE TRADE"):
        assert banned not in blob


def test_scan_universe_aggregates(monkeypatch):
    u = cp.scan_universe("15m")
    assert set(r["instrument"] for r in u["instruments"]) == set(cp.INTRADAY_UNIVERSE)
    assert isinstance(u["conditions_active_somewhere"], dict)


# --- C. base rate ---------------------------------------------------
def test_base_rate_forward_outcomes_and_verdict():
    br = cp.base_rate("EURUSD", "15m", ("TREND_UP",))
    assert br["state"] in ("OK", "TOO_FEW_OCCURRENCES")
    if br["state"] == "OK":
        h4 = br["by_horizon"]["h4"]
        assert h4["state"] == "OK"
        assert 0.0 <= h4["up_rate"] <= 1.0
        assert h4["verdict"].startswith(("NEAR_COIN_FLIP", "WEAK_SKEW", "NOTABLE_SKEW"))
        assert abs(h4["up_rate"] + h4["down_rate"] - 1.0) < 0.05


def test_base_rate_unknown_condition():
    assert cp.base_rate("EURUSD", "15m", ("NOT_A_CONDITION",))["state"] == "UNKNOWN_CONDITION"


def test_forward_outcomes_verdict_thresholds():
    # craft an index set with a strong up bias -> NOTABLE_SKEW
    df = _augmented_frame(n=800, seed=7)
    df["close"] = 100.0 + np.arange(800) * 0.05     # strictly rising
    df["atr"] = 1.0
    idx = np.arange(cp._WARMUP_BARS, 700)
    fo = cp._forward_outcomes(df, idx, 4)
    assert fo["up_rate"] > 0.9 and fo["verdict"].startswith("NOTABLE_SKEW")


# --- D. reward:risk feasibility -----------------------------------
def test_rr_feasibility_breakeven_math():
    br = {"by_horizon": {"h4": {"state": "OK", "up_rate": 0.55, "down_rate": 0.45}}}
    f = cp.rr_feasibility(br, "long", 2.0, horizon=4)
    assert abs(f["breakeven_win_rate"] - 1 / 3) < 1e-3
    assert f["historical_move_rate_in_direction"] == 0.55
    assert f["label"] == "PLAUSIBLE_IF_DIRECTION_READ_IS_SOUND"
    f2 = cp.rr_feasibility(br, "short", 0.8, horizon=4)   # be_win ~0.56 vs 0.45
    assert f2["label"] == "UNLIKELY_TO_BE_POSITIVE_EXPECTANCY"


# --- E. journal + skill --------------------------------------
def test_log_setup_and_outcome_realized_r():
    r = cp.log_setup("EURUSD", "15m", "long", entry=100.0, stop=99.0, target=103.0, tag="sweep-rc")
    assert r["state"] == "LOGGED"
    sid = r["setup"]["setup_id"]
    assert r["setup"]["reward_risk"] == 3.0
    o = cp.log_outcome(sid, exit_price=102.0, outcome_note="partial")
    assert o["state"] == "RESOLVED"
    assert o["setup"]["realized_r"] == 2.0            # (102-100)/1.0
    # a short that goes against
    r2 = cp.log_setup("XAUUSD", "1h", "short", entry=2000.0, stop=2010.0, target=1970.0, tag="x")
    o2 = cp.log_outcome(r2["setup"]["setup_id"], exit_price=2010.0)
    assert o2["setup"]["realized_r"] == -1.0


def test_skill_report_insufficient_then_verdict(monkeypatch):
    assert cp.skill_report()["state"] == "INSUFFICIENT_SAMPLE"
    # inject 32 resolved setups that beat their base rate handily
    setups = []
    for i in range(32):
        setups.append({"setup_id": f"s{i}", "status": "RESOLVED", "realized_r": 1.5, "direction": "long",
                       "tag": "t", "reward_risk": 2.0,
                       "base_rate_at_log": {"state": "OK", "up_rate": 0.5, "down_rate": 0.5}})
    monkeypatch.setattr(cp, "_load_journal", lambda: setups)
    rep = cp.skill_report()
    assert rep["state"] == "OK" and rep["n_resolved"] == 32
    assert rep["verdict"] == "SELECTION_ADDS_EDGE"


# --- F. evaluate ------------------------------------------------
def test_evaluate_setup_structure():
    ev = cp.evaluate_setup("EURUSD", "15m", "long", entry=100.0, stop=99.5, target=101.5, tag="adhoc")
    assert ev["state"] == "OK"
    for k in ("scan", "base_rate", "reward_risk_feasibility", "your_track_record", "macro", "summary"):
        assert k in ev
    assert "does not tell you to take the trade" in ev["summary"].lower()


def test_evaluate_setup_unknown_instrument():
    assert cp.evaluate_setup("BTCUSD", "15m", "long", 1, 0.9, 1.3)["state"] == "UNKNOWN_INSTRUMENT"


# --- G. determinism + persistence --------------------------
def test_run_and_persist_roundtrip():
    res = cp.run()
    assert res.determinism["match"] is True
    cp.persist(res)
    got = cp.get_result()
    assert got["schema_version"] == cp.SCHEMA_VERSION
    assert got["live_automation_enabled"] is False
    assert got["holdout_untouched"] is True


# --- H. safety ------------------------------------------------
def test_no_execution_imports_or_holdout_read():
    src = inspect.getsource(cp)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    for f in ("order_execution", "broker_adapter", "execution_pipeline", "risk_engine",
              "account_management", "paper_simulator", "trade_setup_engine"):
        assert not any(re.search(rf"\b{f}\b", l) for l in import_lines), f"forbidden import: {f}"
    for token in ("place_order", "submit_order", "execute_trade", "load_holdout", "locked_holdout"):
        assert token not in src


def test_frozen_contract_hash_is_the_canonical_constant():
    import gold_strategy_baseline as gsb
    assert gsb.get_gold_baseline().frozen_contract_hash == gsb.CANONICAL_CONTRACT_HASH


# --- I. API ---------------------------------------------------
def test_api_endpoint_get_only_and_safe():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    r = client.get("/api/research/intraday-copilot")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] in ("NOT_COMPUTED", "AVAILABLE")
    assert body["safety_barrier"] == {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}
    assert client.post("/api/research/intraday-copilot").status_code == 405
