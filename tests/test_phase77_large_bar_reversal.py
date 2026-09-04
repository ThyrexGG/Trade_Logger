# -*- coding: utf-8 -*-
"""
Phase 77 — large-bar reversal candidate validation.

Deterministic H8 event reproduction (exact Phase 76 definition), large-bar
detection, ATR, event/fade direction, entry timing, no look-ahead, stop/target
walk, realistic cost application, retest-limit handling, regime / volatility /
session conditioning, OOS boundary, deterministic bootstrap + artifact.
Synthetic bars — no full data run.
"""
import importlib
import inspect

import numpy as np
import pandas as pd

import historical_data_store as _store
import phase76_event_study as p76
import phase77_large_bar_reversal as p


def _frame(n=8000, seed=5, big_every=40, big_size=1.2):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0, 1.0, n).cumsum()
    close = 100.0 + steps * 0.03
    high = close + np.abs(rng.normal(0, 0.05, n))
    low = close - np.abs(rng.normal(0, 0.05, n))
    open_ = close - rng.normal(0, 0.02, n)
    for k in range(200, n, big_every):                 # inject large BULLISH bars
        open_[k] = close[k] - big_size * 0.8
        high[k] = close[k] + big_size * 0.2
        low[k] = open_[k] - big_size * 0.05
    t0 = 1_600_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": 100.0, "source": "mt5"} for i in range(n)]


def _load(monkeypatch, rows, inst="EURUSD", tf="15m"):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(_store, "get_candles", lambda i, t: rows)
    p._clear_bar_cache()                     # never serve a stale synthetic frame
    df = p.load_bars(inst, tf)
    return df


# --- H8 event reproduction ------------------------------------------
def test_h8_event_matches_phase76_exactly(monkeypatch):
    rows = _frame()
    df = _load(monkeypatch, rows)
    a_idx, a_dir, a_mag = p.large_bar_events(df, 1.5)
    b_idx, b_dir, b_mag = p76._b_range_expansion(df, 1.5)
    assert list(a_idx) == list(np.asarray(b_idx, int))
    np.testing.assert_allclose(a_dir, np.asarray(b_dir, float))
    np.testing.assert_allclose(a_mag, np.asarray(b_mag, float), equal_nan=True)


def test_large_bar_detection_uses_tr_over_atr_threshold(monkeypatch):
    df = _load(monkeypatch, _frame())
    idx, _d, mag = p.large_bar_events(df, 1.5)
    # every flagged bar has tr/ATR >= 1.5 and index >= 20 (Phase 76 min_index)
    assert (mag >= 1.5 - 1e-9).all()
    assert (idx >= 20).all()
    # a higher threshold is a strict subset
    idx2, _e, _m = p.large_bar_events(df, 2.0)
    assert set(idx2).issubset(set(idx))


def test_atr_is_sma14_of_true_range(monkeypatch):
    df = _load(monkeypatch, _frame())
    c = df["close"].to_numpy(); h = df["high"].to_numpy(); l = df["low"].to_numpy()
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
    expect = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
    np.testing.assert_allclose(df["atr"].to_numpy(), expect, equal_nan=True)


# --- fade direction / entry / no lookahead --------------------------
def test_fade_direction_opposes_the_large_bar(monkeypatch):
    df = _load(monkeypatch, _frame())
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    idx, direction, _m = p.large_bar_events(df, 1.5)
    checked = 0
    for pos, i in enumerate(idx):
        if direction[pos] == 0 or i >= len(c) - 2:
            continue
        sim = p._simulate(o, h, l, c, atr, int(i), direction[pos],
                          "next_bar_market", "revert_to_event_open", 8)
        if sim is None:
            continue
        # large bullish bar -> SHORT fade, and vice versa
        assert sim["fade_dir"] == ("SHORT" if direction[pos] > 0 else "LONG")
        checked += 1
    assert checked > 20


def test_entry_is_next_bar_open_no_lookahead(monkeypatch):
    df = _load(monkeypatch, _frame())
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    idx, direction, _m = p.large_bar_events(df, 1.5)
    i = int(idx[5])
    sim = p._simulate(o, h, l, c, atr, i, direction[5], "next_bar_market",
                      "revert_to_event_open", 8)
    assert sim is not None
    assert sim["entry_idx"] == i + 1
    assert abs(sim["entry_price"] - o[i + 1]) < 1e-5
    # truncating everything after the exit bar must not change the trade
    cut = sim["exit_idx"] + 1
    s2 = p._simulate(o[:cut], h[:cut], l[:cut], c[:cut], atr[:cut], i, direction[5],
                     "next_bar_market", "revert_to_event_open", 8)
    assert (s2["entry_price"], s2["stop"], s2["target"], s2["exit_price"]) == \
           (sim["entry_price"], sim["stop"], sim["target"], sim["exit_price"])


def test_stop_sits_beyond_the_large_bar_extreme(monkeypatch):
    df = _load(monkeypatch, _frame())
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    idx, direction, _m = p.large_bar_events(df, 1.5)
    i = int(idx[7])
    sim = p._simulate(o, h, l, c, atr, i, direction[7], "next_bar_market",
                      "revert_to_event_open", 8)
    if sim and sim["fade_dir"] == "SHORT":
        assert sim["stop"] > h[i]          # above the large-bar high
        assert sim["target"] == round(float(o[i]), 6)   # event open


def test_retest_limit_entry_needs_a_touch_within_window(monkeypatch):
    df = _load(monkeypatch, _frame())
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    idx, direction, _m = p.large_bar_events(df, 1.5)
    fills = 0
    for pos, i in enumerate(idx[:40]):
        if direction[pos] == 0 or i >= len(c) - 6:
            continue
        sim = p._simulate(o, h, l, c, atr, int(i), direction[pos],
                          "retest_limit_50", "revert_to_event_open", 8)
        if sim is None:
            continue
        fills += 1
        # limit fill happens within the pre-registered window
        assert i + 1 <= sim["entry_idx"] <= i + p._LIMIT_ENTRY_WINDOW
    assert fills >= 1


def test_confirm_delay_requires_a_confirming_bar(monkeypatch):
    src = inspect.getsource(p._simulate)
    assert 'moved != d' in src and "entry_idx, entry_px = i + 2" in src


# --- costs ---------------------------------------------------------
def test_costs_reduce_r_and_are_two_sided(monkeypatch):
    df = _load(monkeypatch, _frame())
    s = p.run_instrument("EURUSD", "15m", {"mult": 1.5})
    assert s["state"] == "OK" and s["n_trades"] > 50
    for t in s["trades"][:50]:
        assert t["r_net"] < t["r_gross"]                  # friction always costs
        # the ATR cost grid is monotstonically worse with higher assumed cost
        g = t["r_net_cost_grid"]
        assert g["0.025"] > g["0.05"] > g["0.075"] > g["0.1"]


def test_cost_model_documents_missing_spread_history():
    src = inspect.getsource(p)
    assert "historical_spread_available" in src
    assert "mid-price OHLCV" in src


# --- OOS boundary ------------------------------------------------
def test_oos_split_is_chronological_by_event_bar_index(monkeypatch):
    df = _load(monkeypatch, _frame())
    s = p.run_instrument("EURUSD", "15m", {"mult": 1.5})
    dev = [t for t in s["trades"] if t["split"] == "dev"]
    oos = [t for t in s["trades"] if t["split"] == "oos"]
    assert dev and oos
    assert max(t["event_time"] for t in dev) < min(t["event_time"] for t in oos)
    # boundary at 70% of the bar count
    assert abs(s["dev_oos_boundary_ts"] - df["t"].to_numpy()[int(len(df) * 0.7)]) < 1e-6


# --- segmentation ----------------------------------------------
def test_regime_and_vol_buckets_are_causal_labels(monkeypatch):
    df = _load(monkeypatch, _frame())
    assert set(df["regime"].unique()).issubset({"TRENDING", "RANGING", "MIXED"})
    assert set(df["vol_bucket"].unique()).issubset(
        {"LOW_VOL", "NORMAL_VOL", "HIGH_VOL", "UNKNOWN"})
    # vol_bucket derives from the Phase 76 trailing-200-bar atr_rank (no future info)
    src = inspect.getsource(p.load_bars)
    assert 'df["atr_rank"]' in src


def test_segment_marks_thin_buckets_insufficient():
    trades = [{"split": "oos", "regime": "RANGING", "r_net": 0.1, "r_gross": 0.1,
               "event_time": f"t{i}", "bars_held": 3, "mae_r": 0, "mfe_r": 0,
               "exit_reason": "TARGET", "r_net_cost_grid": {"0.025": 0.1, "0.05": 0.1,
                                                            "0.075": 0.1, "0.1": 0.1}}
              for i in range(10)]
    seg = p._segment(trades, "regime", split="oos", min_n=30)
    assert seg["RANGING"]["status"] == "INSUFFICIENT_SAMPLE"


# --- gate --------------------------------------------------------
def test_gate_never_promotes_weak_or_negative_oos():
    neg = [{"r_net": -0.2, "r_gross": -0.1, "event_time": f"2024-{1+i//25:02d}-{1+i%25:02d}",
            "bars_held": 3, "mae_r": -0.5, "mfe_r": 0.1, "exit_reason": "STOP",
            "r_net_cost_grid": {"0.025": -0.15, "0.05": -0.2, "0.075": -0.25, "0.1": -0.3}}
           for i in range(150)]
    g = p._gate(neg, neighbourhood_stable=True, cross_asset="UNIVERSAL", temporal_ok=True)
    assert g["gate"] == "FAIL"
    tiny = [{"r_net": 5.0, "r_gross": 5.0, "event_time": f"t{i}", "bars_held": 1,
             "mae_r": 0, "mfe_r": 5, "exit_reason": "TARGET",
             "r_net_cost_grid": {"0.025": 5, "0.05": 5, "0.075": 5, "0.1": 5}}
            for i in range(10)]
    assert p._gate(tiny, neighbourhood_stable=True, cross_asset="UNIVERSAL",
                   temporal_ok=True)["gate"] == "INSUFFICIENT_DATA"


def test_gate_requires_cost_survival_and_cross_asset_for_go():
    # positive but only survives to below base cost -> not GO
    pos = [{"r_net": 0.02, "r_gross": 0.09, "event_time": f"2024-{1+i//25:02d}-{1+i%25:02d}",
            "bars_held": 4, "mae_r": -0.3, "mfe_r": 0.5, "exit_reason": "TARGET",
            "r_net_cost_grid": {"0.025": 0.03, "0.05": -0.01, "0.075": -0.05, "0.1": -0.1}}
           for i in range(200)]
    g = p._gate(pos, neighbourhood_stable=True, cross_asset="UNIVERSAL", temporal_ok=True)
    assert g["gate"] in ("FAIL", "UNCERTAIN")            # base-cost survival fails


def test_cross_asset_class_needs_multiple_assets():
    one = {"EURUSD": {"oos_metrics": {"mean_r": 0.1}, "bootstrap_ci": {"ci_lower": 0.02}}}
    assert p._cross_asset_class(one) == "SINGLE_ASSET"
    jpy = {"AUDJPY": {"oos_metrics": {"mean_r": 0.1}, "bootstrap_ci": {"ci_lower": 0.03}},
           "GBPJPY": {"oos_metrics": {"mean_r": 0.08}, "bootstrap_ci": {"ci_lower": 0.01}}}
    assert p._cross_asset_class(jpy) == "JPY_SPECIFIC"
    none = {"EURUSD": {"oos_metrics": {"mean_r": -0.1}, "bootstrap_ci": {"ci_lower": -0.2}}}
    assert p._cross_asset_class(none) == "NONE"


# --- determinism / holdout / safety -----------------------------
def test_run_is_deterministic(monkeypatch):
    rows15 = _frame(n=7000, seed=11)
    rows1h = _frame(n=5000, seed=12)

    def _get(inst, tf):
        return {"15m": rows15, "1h": rows1h}.get(tf, [])

    monkeypatch.setattr(p76.store, "get_candles", _get)
    monkeypatch.setattr(_store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: {"dataset_id": f"{a}:test"})
    monkeypatch.setattr(p, "_git_commit", lambda: "testsha")
    r1 = p.run(("EURUSD", "GBPUSD"))
    r2 = p.run(("EURUSD", "GBPUSD"))
    assert r1.content_hash == r2.content_hash
    assert r1.verdict == r2.verdict
    assert r1.candidate_gates == r2.candidate_gates
    assert r1.holdout_untouched is True


def test_run_is_conservative_on_random_walk(monkeypatch):
    def _get(inst, tf):
        n = {"15m": 7000, "1h": 5000}[tf]
        return _frame(n=n, seed=(hash((inst, tf)) % 9991), big_every=45, big_size=1.0)
    monkeypatch.setattr(p76.store, "get_candles", _get)
    monkeypatch.setattr(_store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    monkeypatch.setattr(p, "_git_commit", lambda: None)
    r = p.run(("EURUSD", "GBPUSD", "AUDJPY"))
    assert r.verdict in ("NO_VALIDATED_CANDIDATE", "PROMISING BUT UNCERTAIN",
                         "INSUFFICIENT_DATA")
    gates = [g if isinstance(g, str) else g.get("gate") for g in r.candidate_gates.values()]
    assert "GO" not in gates                       # random walk must not produce a candidate
    assert r.verdict != "VALIDATED CANDIDATE"


def test_h8_definition_is_not_redefined():
    src = inspect.getsource(p)
    # the event set comes straight from Phase 76 — no local re-implementation
    assert "_b_range_expansion" in src
    assert "from phase76_event_study import" in src


def test_no_execution_or_broker_imports():
    src = inspect.getsource(p)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
                "order_execution", "live_trading", "live_automation"):
        assert bad not in src


def test_frozen_holdout_is_never_read():
    src = inspect.getsource(p)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
                "forward_lifecycle", "HistoricalVsForwardComparator",
                "get_holdout", "holdout_trades", "load_holdout", "holdout_df",
                "holdout_candles", "read_holdout"):
        assert bad not in src
    # 'holdout' appears only in prose ("the frozen holdout is never read") and in
    # the reported `holdout_untouched` field — never as a data access
    import re
    bare = re.findall(r"holdout(?!_untouched)", src.lower())
    assert len(bare) == 1  # the one docstring sentence


def test_frozen_hash_and_safety_flags_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"


def test_no_ml_or_optimization_in_module():
    src = inspect.getsource(p).lower()
    for bad in ("sklearn", "tensorflow", "torch", "lstm", "xgboost",
                "gridsearch", "optimize", "minimize("):
        assert bad not in src


def test_primary_registry_is_small():
    assert len(p.PRIMARY_HYPOTHESES) == 4
    assert p._BONF_ALPHA == round(0.05 / 4, 10)


def test_module_imports_clean():
    importlib.reload(p)
    assert hasattr(p, "run") and hasattr(p, "get_result")
    assert p.PRIMARY_INSTRUMENTS == ("AUDJPY", "GBPJPY", "GBPUSD", "EURUSD")
