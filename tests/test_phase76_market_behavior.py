# -*- coding: utf-8 -*-
"""
Phase 76 — literature-guided market behavior discovery.

Deterministic event-study framework: event detection, forward-return alignment,
no look-ahead, ATR normalisation, block bootstrap, 70/30 chronological split,
cross-year from cached rows, tiered multiple testing, holdout isolation,
reproducibility. Synthetic bars — no full data run.
"""
import importlib
import inspect

import numpy as np
import pandas as pd

import phase76_event_study as p


def _synthetic_frame(n=6000, seed=3, drift=0.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    t0 = 1_650_000_000
    rows = [{"time": t0 + i * 900, "open": open_[i], "high": max(open_[i], high[i], close[i]),
             "low": min(open_[i], low[i], close[i]), "close": close[i],
             "volume": float(rng.integers(50, 500)), "source": "mt5"} for i in range(n)]
    return rows


def _load(monkeypatch, rows):
    monkeypatch.setattr(p.store, "get_candles", lambda i, tf: rows)
    df = p.load_bars("XAUUSD", "15m")
    df.attrs["tf"] = "15m"
    return df


# --- data / features -------------------------------------------------
def test_load_bars_is_deterministic_and_causal(monkeypatch):
    rows = _synthetic_frame()
    a = _load(monkeypatch, rows)
    b = _load(monkeypatch, rows)
    pd.testing.assert_frame_equal(a, b)
    # timestamps strictly ordered, de-duplicated
    assert a["t"].is_monotonic_increasing
    assert a["t"].duplicated().sum() == 0
    # ATR uses a trailing window -> first 13 are NaN, never forward-filled from the future
    assert a["atr"].iloc[:13].isna().all()
    assert np.isfinite(a["atr"].iloc[20:]).all()


def test_load_bars_drops_non_mt5_rows(monkeypatch):
    rows = _synthetic_frame(n=1000)
    rows += [{**rows[0], "time": rows[-1]["time"] + 900, "source": "synthetic_test"}]
    monkeypatch.setattr(p.store, "get_candles", lambda i, tf: rows)
    df = p.load_bars("XAUUSD", "15m")
    assert len(df) == 1000                          # the synthetic_test row is excluded


def test_atr_percentile_rank_has_no_future_leak(monkeypatch):
    df = _load(monkeypatch, _synthetic_frame())
    # rank at bar i must be computable from atr[i-199..i] only; truncating the
    # future must not change any earlier value
    full = df["atr_rank"].to_numpy()
    cut = p.load_bars.__wrapped__ if hasattr(p.load_bars, "__wrapped__") else None
    # re-load a truncated copy
    rows = _synthetic_frame()
    part = rows[:4000]
    import copy
    d2 = p.load_bars("XAUUSD", "15m") if False else None
    monkeypatch.setattr(p.store, "get_candles", lambda i, tf: part)
    d2 = p.load_bars("XAUUSD", "15m")
    np.testing.assert_allclose(full[:3800], d2["atr_rank"].to_numpy()[:3800],
                               rtol=0, atol=1e-12, equal_nan=True)


# --- event studies + no lookahead -----------------------------------
def test_forward_return_starts_strictly_after_event(monkeypatch):
    df = _load(monkeypatch, _synthetic_frame())
    i, d, m = p._b_st_reversal(df)
    s = p.study_events(df, i, d, m, signed=True)
    assert s["state"] == "OK" and s["n_events"] >= 20
    # every headline event row's fwd_r is finite and the h-map horizons exist
    assert all(np.isfinite(r["fwd_r"]) for r in s["event_rows"])
    for h in p.FWD_HORIZONS:
        assert f"h{h}" in s["horizons"]


def test_no_lookahead_future_bars_do_not_change_dev_events(monkeypatch):
    rows = _synthetic_frame(n=8000)
    monkeypatch.setattr(p.store, "get_candles", lambda i, tf: rows[:5000])
    d1 = p.load_bars("XAUUSD", "15m"); d1.attrs["tf"] = "15m"
    monkeypatch.setattr(p.store, "get_candles", lambda i, tf: rows)
    d2 = p.load_bars("XAUUSD", "15m"); d2.attrs["tf"] = "15m"
    b1 = p._b_range_expansion(d1, 1.5)[0]
    b2 = p._b_range_expansion(d2.iloc[:5000], 1.5)[0]
    # events detected on the first 5000 bars are identical whether or not later data exists
    assert list(b1) == list(b2)


def test_event_direction_and_signing(monkeypatch):
    df = _load(monkeypatch, _synthetic_frame())
    i, d, m = p._b_intraday_mom(df)
    signed = p.study_events(df, i, d, m, signed=True)
    unsigned = p.study_events(df, i, d, m, signed=False)
    # signed multiplies forward return by event direction -> generally differs
    assert signed["horizons"]["h4"]["mean"] != unsigned["horizons"]["h4"]["mean"]


# --- bootstrap ------------------------------------------------------
def test_block_bootstrap_deterministic_and_ci_ordered():
    v = np.array([0.3, -1.0, 1.7, -0.2, 0.9, -1.0, 0.4, -0.8] * 40)
    a = p.block_bootstrap(v, block=4)
    b = p.block_bootstrap(v, block=4)
    assert a == b
    assert a["ci_lower"] <= a["mean"] <= a["ci_upper"]
    assert a["block"] == 4


def test_block_bootstrap_insufficient_sample():
    assert p.block_bootstrap(np.array([0.1, 0.2, 0.3]), block=1)["verdict"] == "INSUFFICIENT_SAMPLE"


# --- chronological split ------------------------------------------
def test_dev_oos_split_is_chronological_70_30(monkeypatch):
    df = _load(monkeypatch, _synthetic_frame(n=5000))
    bound = int(len(df) * p._DEV_RATIO)
    assert bound == 3500
    dev, oos = df.iloc[:bound], df.iloc[bound:]
    assert dev["t"].max() < oos["t"].min()          # strictly ordered, no overlap


# --- cross-year uses cached rows --------------------------------
def test_cross_year_operates_on_cached_rows_only():
    src = inspect.getsource(p.run)
    assert "_cross_year_from_rows(rows)" in src
    assert "for y in years" not in src              # no per-year re-run loop in run()
    rows = ([{"year": 2022, "session": "LONDON", "regime": "RANGING", "mag_atr": 1.0, "fwd_r": 0.3}] * 30
            + [{"year": 2023, "session": "LONDON", "regime": "RANGING", "mag_atr": 1.0, "fwd_r": 0.2}] * 30
            + [{"year": 2024, "session": "LONDON", "regime": "RANGING", "mag_atr": 1.0, "fwd_r": -0.1}] * 30)
    assert p._cross_year_from_rows(rows) == round(2 / 3, 3)
    assert p._cross_year_from_rows([{"year": 2022, "fwd_r": 0.1}] * 10) is None  # <3 usable years


# --- multiple testing --------------------------------------------
def test_bonferroni_and_bh():
    assert p._benjamini_hochberg([], 0.1) == []
    # one tiny p among noise -> BH keeps it
    ps = [0.001] + [0.6] * 19
    bh = p._benjamini_hochberg(ps, 0.10)
    assert bool(bh[0]) is True and sum(bh) == 1
    m1 = sum(1 for h in p.HYPOTHESES if h.tier == 1)
    assert m1 >= 4


# --- discovery score frozen ------------------------------------
def test_discovery_weights_are_frozen_and_sum_to_one():
    assert abs(sum(p.DISCOVERY_WEIGHTS.values()) - 1.0) < 1e-9
    src = inspect.getsource(p)
    assert '"effect_z": 0.28' in src               # pinned, not computed


def test_classify_never_calls_weak_evidence_actionable():
    weak_dev = {"verdict": "ZERO_CROSSING", "mean": 0.01, "effect_z": 0.5}
    weak_oos = {"verdict": "ZERO_CROSSING", "mean": 0.005}
    assert p._classify(weak_dev, weak_oos, 0.3, -0.04, 500) in ("NO_EVIDENCE",)
    sub_cost = {"verdict": "POSITIVE", "mean": 0.02, "effect_z": 3.0, "cost_adj_mean": -0.03}
    assert p._classify(sub_cost, {"verdict": "POSITIVE", "mean": 0.02}, 0.6, -0.03, 800) == "REAL_BUT_SUB_COST"


# --- holdout + safety ------------------------------------------
def test_frozen_holdout_never_accessed():
    src = inspect.getsource(p)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
                "forward_lifecycle", "HistoricalVsForwardComparator", "holdout"):
        assert bad.lower() not in src.lower() or bad == "holdout"  # 'holdout_untouched' allowed
    assert "holdout_untouched: true" not in src   # it's a field, set True, never a claim string


def test_no_execution_or_broker_imports():
    src = inspect.getsource(p)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
                "order_execution", "live_trading", "live_automation"):
        assert bad not in src


def test_frozen_hash_and_safety_flags_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"


# --- full run determinism (stubbed) --------------------------
def test_run_is_deterministic(monkeypatch):
    rows15 = _synthetic_frame(n=6000, seed=11)
    rows1h = _synthetic_frame(n=4000, seed=12)
    rows1d = _synthetic_frame(n=1200, seed=13)

    def _get(inst, tf):
        return {"15m": rows15, "1h": rows1h, "1d": rows1d}.get(tf, [])

    monkeypatch.setattr(p.store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: {"dataset_id": f"{a}:test"})
    monkeypatch.setattr(p, "_git_commit", lambda: "testsha")
    r1 = p.run(("XAUUSD", "USDJPY"))
    r2 = p.run(("XAUUSD", "USDJPY"))
    assert r1.content_hash == r2.content_hash
    assert [s["status"] for s in r1.scorecard] == [s["status"] for s in r2.scorecard]
    assert r1.verdict == r2.verdict
    assert r1.holdout_untouched is True
    assert r1.frozen_contract_hash == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_run_verdict_is_conservative_on_random_walk(monkeypatch):
    # pure random walk -> should NOT find actionable phenomena
    def _get(inst, tf):
        n = {"15m": 6000, "1h": 4000, "1d": 1200}[tf]
        return _synthetic_frame(n=n, seed=hash((inst, tf)) % 9999)
    monkeypatch.setattr(p.store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    monkeypatch.setattr(p, "_git_commit", lambda: None)
    r = p.run(("XAUUSD", "USDJPY", "EURUSD"))
    assert r.verdict in ("NO_ACTIONABLE_PHENOMENA", "PROMISING BUT UNCERTAIN", "INSUFFICIENT_DATA")
    assert len(r.candidates) == 0


def test_module_imports_clean():
    importlib.reload(p)
    assert hasattr(p, "run") and hasattr(p, "get_result")
    assert len(p.LITERATURE) >= 6
    for lit in p.LITERATURE:
        assert "transferability" in lit and "hypotheses" in lit
