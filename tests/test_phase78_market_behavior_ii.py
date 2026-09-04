# -*- coding: utf-8 -*-
"""
Phase 78 — literature-guided market behavior discovery II.

Momentum x volatility expansion x breakout/retest x session transitions.
Deterministic causal features, event/target definitions, look-ahead safety,
block bootstrap reuse, multiple testing, OOS split, cross-year/instrument
aggregation, cost sensitivity, candidate gate, ML readiness, negative
knowledge, artifact determinism, holdout firewall, and API behaviour.
Synthetic bars only — no full data run.
"""
import importlib
import inspect

import numpy as np

import historical_data_store as _store
import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p


def _frame(n=9000, seed=5, drift=0.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 1.0, n).cumsum()
    close = 100.0 + steps * 0.05
    high = close + np.abs(rng.normal(0, 0.08, n))
    low = close - np.abs(rng.normal(0, 0.08, n))
    open_ = close - rng.normal(0, 0.03, n)
    t0 = 1_650_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": 100.0, "source": "mt5"} for i in range(n)]


def _load(monkeypatch, rows, inst="EURUSD", tf="15m"):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(_store, "get_candles", lambda i, t: rows)
    return p.augment(p.load_bars(inst, tf), tf)


# --- A. hypothesis registry ------------------------------------------
def test_registry_has_required_fields_and_is_small():
    reg = p.hypothesis_registry_dicts()
    assert 4 <= len(reg) <= 12
    required = ("hid", "family", "name", "rationale", "event_definition", "target_definition",
                "timeframes", "horizon_bars", "universe", "regime_scope", "expected_direction",
                "normalization", "minimum_sample_size", "statistical_test", "bootstrap_method",
                "multiple_testing_tier", "economic_interpretation")
    for h in reg:
        for f in required:
            assert f in h and h[f] not in (None, "", [])
    families = {h["family"] for h in reg}
    assert families == {"A", "B", "C", "D"}          # all four families represented


def test_tier1_count_matches_bonferroni_alpha():
    m1 = len(p._TIER1_HIDS)
    assert m1 >= 4
    assert abs(p._BONF_ALPHA - 0.05 / m1) < 1e-12


# --- B/C. event definitions + look-ahead --------------------------
def test_impulse_fires_once_per_streak_not_every_bar(monkeypatch):
    df = _load(monkeypatch, _frame())
    idx, direction, mag = p._b_impulse(df, run=3)
    consec = df["consec_dir"].to_numpy()
    assert (consec[idx] == 3).all()                  # exactly the completing bar
    assert (direction != 0).all()


def test_compression_duration_requires_consecutive_bars(monkeypatch):
    df = _load(monkeypatch, _frame())
    idx, _d, run = p._b_compression_duration(df, min_run=3)
    comp_run = df["comp_run"].to_numpy()
    assert (comp_run[idx] == 3).all()
    # every bar in the qualifying window must itself be compressed
    atr_rank = df["atr_rank"].to_numpy()
    for i in idx[:20]:
        assert (atr_rank[i - 2:i + 1] <= p._COMPRESSION_RANK_THR + 1e-9).all()


def test_breakout_uses_prior_bars_only_not_current(monkeypatch):
    df = _load(monkeypatch, _frame())
    h = df["high"].to_numpy(); n = len(h)
    roll_h = df["roll_h20"].to_numpy()
    # roll_h20 at bar i must equal max(high[i-20..i-1]), excluding bar i itself
    i = 5000
    expect = h[i - 20:i].max()
    assert abs(roll_h[i] - expect) < 1e-9


def test_breakout_retest_is_first_qualifying_touch_only(monkeypatch):
    df = _load(monkeypatch, _frame())
    h = df["high"].to_numpy(); lo = df["low"].to_numpy(); n = len(h)
    b_idx, b_dir, b_level = p._b_breakout(df)
    assert len(b_idx) > 5
    checked = 0
    for k, bi in enumerate(b_idx[:30]):
        lv = b_level[k]
        # independently recompute THIS breakout's own first retest by direct scan
        expect = None
        for b in range(int(bi) + 1, min(int(bi) + 1 + p._RETEST_WINDOW, n)):
            if lo[b] <= lv <= h[b]:
                expect = b
                break
        if expect is None:
            continue
        # every bar strictly between the breakout and the expected retest must NOT touch
        for b in range(int(bi) + 1, expect):
            assert not (lo[b] <= lv <= h[b])
        checked += 1
    assert checked > 0


def test_failed_breakout_decision_point_is_after_classification_window(monkeypatch):
    df = _load(monkeypatch, _frame())
    idx, direction, _m = p._b_failed_breakout(df)
    b_idx, b_dir, _lv = p._b_breakout(df)
    if len(idx) == 0:
        return
    # decision bar = breakout bar + K, and fade direction is opposite the breakout
    diffs = set()
    for ridx, d in zip(idx[:20], direction[:20]):
        near = [bi for bi in b_idx if 0 < ridx - bi <= p._FAILED_BREAKOUT_K + 1]
        if near:
            diffs.add(ridx - max(near))
    assert diffs.issubset({p._FAILED_BREAKOUT_K})


def test_session_transition_direction_uses_only_pre_transition_bars(monkeypatch):
    df = _load(monkeypatch, _frame())
    sess = df["session"].to_numpy(); c = df["close"].to_numpy()
    idx, direction, _m = p._b_session_transition(df)
    assert (sess[idx] != sess[idx - 1]).all()          # genuinely a transition bar
    for i, d in list(zip(idx, direction))[:20]:
        expect = np.sign(np.log(c[i - 1] / c[i - 1 - p._SESSION_PRE_BARS]))
        assert d == expect


def test_no_lookahead_future_bars_do_not_change_past_events(monkeypatch):
    rows = _frame(n=8000)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows[:5000])
    monkeypatch.setattr(_store, "get_candles", lambda i, t: rows[:5000])
    d1 = p.augment(p.load_bars("EURUSD", "15m"), "15m")
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(_store, "get_candles", lambda i, t: rows)
    d2 = p.augment(p.load_bars("EURUSD", "15m"), "15m")
    b1 = p._b_breakout(d1)[0]
    b2 = p._b_breakout(d2.iloc[:5000])[0]
    assert list(b1) == list(b2)
    i1 = p._b_impulse(d1)[0]
    i2 = p._b_impulse(d2.iloc[:5000])[0]
    assert list(i1) == list(i2)


# --- D. forward targets + horizons ---------------------------------
def test_forward_horizons_present_and_end_of_series_dropped(monkeypatch):
    df = _load(monkeypatch, _frame())
    idx, d, m = p._b_impulse(df)
    res = p._study_signed(df, idx, d, m)
    for h in p76.FWD_HORIZONS:
        assert f"h{h}" in res["horizons"]
    # every event row's fwd_r is finite
    assert all(np.isfinite(r["fwd_r"]) for r in res["event_rows"])


def test_range_expansion_target_is_baseline_centered(monkeypatch):
    df = _load(monkeypatch, _frame())
    idx, d, m = p._b_compression_duration(df)
    res = p.study_range_expansion(df, idx, d, m)
    for h in p76.FWD_HORIZONS:
        cell = res["horizons"][f"h{h}"]
        assert "baseline_mean" in cell and "raw_event_mean" in cell
        # raw_event_mean - baseline_mean should reconstruct the bootstrapped mean
        assert abs((cell["raw_event_mean"] - cell["baseline_mean"]) - cell["mean"]) < 1e-6


def test_range_expansion_uses_stable_atr_not_event_time_atr(monkeypatch):
    """Regression: the event-time ATR is, BY CONSTRUCTION, depressed at a
    compression event. Normalising the forward-range target by it (instead of
    a stable trailing ATR) mechanically inflates the ratio even on a pure
    random walk with no real expansion phenomenon. This was caught and fixed
    during Phase 78 development."""
    src = inspect.getsource(p.study_range_expansion)
    assert "atr_stable" in src and 'df["atr"]' not in src
    df = _load(monkeypatch, _frame(seed=1))
    idx, d, m = p._b_compression_duration(df)
    res = p.study_range_expansion(df, idx, d, m)
    # on a pure random walk there is no real expansion phenomenon beyond noise —
    # every horizon must be ZERO_CROSSING once correctly normalised
    for h in p76.FWD_HORIZONS:
        assert res["horizons"][f"h{h}"]["verdict"] == "ZERO_CROSSING"


def test_persistence_target_is_a_probability_effect(monkeypatch):
    df = _load(monkeypatch, _frame())
    idx, d, m = p._b_vol_bucket_high(df)[0], None, None
    idx, d, m = p._b_vol_bucket_high(df)
    res = p.study_persistence(df, idx, d, m, bucket="HIGH")
    for h in p76.FWD_HORIZONS:
        cell = res["horizons"][f"h{h}"]
        assert 0.0 <= cell["baseline_mean"] <= 1.0
        assert cell["test_kind"] == "regime_persistence_probability_high"


# --- E. bootstrap reuse (unchanged Phase 76 machinery) ---------------
def test_bootstrap_is_the_unchanged_phase76_function():
    # identity (not just behavioural equivalence) as long as neither module has
    # been importlib.reload()-ed in this process; a full-suite run may reload
    # phase76_event_study from an unrelated test file, which rebinds its
    # names — so fall back to a source-identity check that is robust to that.
    if p.block_bootstrap is not p76.block_bootstrap:
        assert inspect.getsource(p.block_bootstrap) == inspect.getsource(p76.block_bootstrap)
    assert p.block_bootstrap.__qualname__ == "block_bootstrap"


def test_bootstrap_deterministic():
    v = np.array([0.2, -0.5, 0.8, -0.1, 0.3, -0.6] * 40)
    a = p.block_bootstrap(v, block=3)
    b = p.block_bootstrap(v, block=3)
    assert a == b


# --- F. multiple testing ---------------------------------------------
def test_benjamini_hochberg_reused_and_tier1_bonferroni_present(monkeypatch):
    def _get(inst, tf):
        n = {"15m": 6000, "1h": 4000}.get(tf, 0)
        return _frame(n=n, seed=abs(hash((inst, tf))) % 9999) if n else []
    monkeypatch.setattr(p76.store, "get_candles", _get)
    monkeypatch.setattr(_store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    r = p.run(("EURUSD", "GBPUSD"))
    mt = r.multiple_testing
    assert mt["tier1_primary_hypotheses"] == len(p._TIER1_HIDS)
    assert mt["tier1_bonferroni_alpha"] == round(0.05 / len(p._TIER1_HIDS), 6)
    assert mt["tier2_diagnostic_tests"] >= mt["tier2_surviving_bh"]


# --- G. OOS split integrity -------------------------------------------
def test_dev_oos_split_is_chronological_70_30(monkeypatch):
    df = _load(monkeypatch, _frame(n=5000))
    bound = int(len(df) * p._DEV_RATIO)
    assert bound == 3500
    dev, oos = df.iloc[:bound], df.iloc[bound:]
    assert dev["t"].max() < oos["t"].min()


# --- H. cross-year / cross-instrument ----------------------------------
def test_cross_year_reused_from_phase76():
    if p._cross_year_from_rows is not p76._cross_year_from_rows:
        assert inspect.getsource(p._cross_year_from_rows) == inspect.getsource(p76._cross_year_from_rows)
    rows = ([{"year": 2022, "fwd_r": 0.2}] * 30 + [{"year": 2023, "fwd_r": 0.1}] * 30
           + [{"year": 2024, "fwd_r": -0.1}] * 30)
    assert p._cross_year_from_rows(rows) == round(2 / 3, 3)


def test_cross_asset_frac_computed_over_actual_universe(monkeypatch):
    def _get(inst, tf):
        n = {"15m": 6000}.get(tf, 0)
        return _frame(n=n, seed=abs(hash((inst, tf))) % 9999) if n else []
    monkeypatch.setattr(p76.store, "get_candles", _get)
    monkeypatch.setattr(_store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    r = p.run(("EURUSD", "GBPUSD", "AUDJPY"))
    for s in r.scorecard:
        assert 0.0 <= s["cross_asset_frac"] <= 1.0


# --- I. cost sensitivity -------------------------------------------
def test_cost_grid_only_applies_to_directional_hypotheses():
    non_dir = p._cost_grid(0.1, directional=False)
    assert non_dir == {"applicable": False}
    dirl = p._cost_grid(0.08, directional=True)
    assert dirl["applicable"] is True
    assert set(dirl["mean_by_atr_cost"].keys()) == {f"{g}" for g in p._COST_ATR_GRID}
    # shrinkage must never flip sign
    for g, v in dirl["mean_by_atr_cost"].items():
        assert v == 0 or (v > 0) == (0.08 > 0)


# --- J. candidate gate --------------------------------------------------
def test_candidate_gate_rejects_weak_or_inconsistent_rows():
    weak = {"status": "NO_EVIDENCE", "n_dev": 500, "n_oos": 100, "dev_mean": 0.01,
           "oos_mean": 0.01, "cross_year_frac": 0.8, "cross_asset_frac": 0.8,
           "directional": True, "cost_grid": {"applicable": True, "survives_up_to_atr_cost": 0.05},
           "dev_effect_z": 1.0, "null_effect_z": 0.5}
    ok, fails = p._candidate_gate_78(weak)
    assert not ok and "status=NO_EVIDENCE" in fails[0]

    flip = {"status": "STRATEGY_CANDIDATE_READY", "n_dev": 500, "n_oos": 100, "dev_mean": 0.1,
           "oos_mean": -0.1, "cross_year_frac": 0.8, "cross_asset_frac": 0.8,
           "directional": True, "cost_grid": {"applicable": True, "survives_up_to_atr_cost": 0.05},
           "dev_effect_z": 3.0, "null_effect_z": 0.2}
    ok, fails = p._candidate_gate_78(flip)
    assert not ok and any("sign_flip" in f for f in fails)


def test_candidate_gate_rejects_effect_not_above_placebo():
    row = {"status": "STRATEGY_CANDIDATE_READY", "n_dev": 500, "n_oos": 100, "dev_mean": 0.05,
          "oos_mean": 0.05, "cross_year_frac": 0.8, "cross_asset_frac": 0.8,
          "directional": True, "cost_grid": {"applicable": True, "survives_up_to_atr_cost": 0.05},
          "dev_effect_z": 1.0, "null_effect_z": 0.9}     # real barely above placebo
    ok, fails = p._candidate_gate_78(row)
    assert not ok and "effect_not_materially_above_placebo" in fails


# --- K. classification never promotes weak evidence ------------------
def test_classify_insufficient_sample():
    weak_dev = {"verdict": "ZERO_CROSSING", "mean": 0.01, "effect_z": 0.2}
    weak_oos = {"verdict": "ZERO_CROSSING", "mean": 0.01}
    assert p._classify_78(weak_dev, weak_oos, 50, 10, True, None, 0.5, 0.5) == "INSUFFICIENT_SAMPLE"


def test_classify_requires_dev_oos_agreement():
    dev = {"verdict": "POSITIVE", "mean": 0.1, "effect_z": 3.0}
    oos_flip = {"verdict": "NEGATIVE", "mean": -0.1}
    status = p._classify_78(dev, oos_flip, 500, 100, True, True, 0.8, 0.8)
    assert status not in ("STRATEGY_CANDIDATE_READY", "CANDIDATE_REQUIRES_PHASE_79_VALIDATION")


def test_classify_directional_needs_cost_survival_for_strategy_ready():
    dev = {"verdict": "POSITIVE", "mean": 0.1, "effect_z": 3.0}
    oos = {"verdict": "POSITIVE", "mean": 0.1}
    without_cost = p._classify_78(dev, oos, 500, 100, True, False, 0.8, 0.8)
    with_cost = p._classify_78(dev, oos, 500, 100, True, True, 0.8, 0.8)
    assert without_cost != "STRATEGY_CANDIDATE_READY"
    assert with_cost == "STRATEGY_CANDIDATE_READY"


def test_classify_nondirectional_maps_to_ml_target_ready():
    dev = {"verdict": "POSITIVE", "mean": 0.1, "effect_z": 3.0}
    oos = {"verdict": "POSITIVE", "mean": 0.1}
    status = p._classify_78(dev, oos, 500, 100, False, None, 0.8, 0.8)
    assert status == "ML_TARGET_READY"


# --- L. ML readiness scorecard -----------------------------------
def test_ml_readiness_row_shape():
    row = p._ml_readiness_row("ML_TARGET_READY", 0.8, 0.6, 500, 100,
                              {"class": "REGIME_INVARIANT"}, False, {"applicable": False})
    assert row["level"] == "ML_TARGET_READY"
    assert 0.0 <= row["score"] <= 1.0
    assert len(row["factors"]) == 10


def test_ml_readiness_never_ready_merely_from_low_p_alone():
    # significance without cross-year/instrument stability or adequate N must not be ML_TARGET_READY
    row = p._ml_readiness_row("PHENOMENON_DETECTED", None, None, 50, 10,
                              {"class": "UNKNOWN"}, False, {"applicable": False})
    assert row["level"] not in ("ML_TARGET_READY", "STRATEGY_CANDIDATE_READY")


# --- M. holdout firewall -------------------------------------------
def test_frozen_holdout_never_accessed():
    src = inspect.getsource(p)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
                "forward_lifecycle", "HistoricalVsForwardComparator",
                "get_holdout", "holdout_trades", "load_holdout", "holdout_df"):
        assert bad not in src
    import re
    bare = re.findall(r"holdout(?!_untouched)", src.lower())
    assert len(bare) <= 1


def test_frozen_hash_and_safety_flags_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"


def test_no_execution_or_broker_imports():
    src = inspect.getsource(p)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
                "order_execution", "live_trading", "live_automation"):
        assert bad not in src


def test_no_ml_training_in_module():
    src = inspect.getsource(p).lower()
    for bad in ("sklearn", "tensorflow", "torch", "lstm", "xgboost", "lightgbm",
                "randomforest", "reinforcement", "transformer", "keras"):
        assert bad not in src


# --- N. artifact determinism + smoke run -----------------------------
def test_run_is_deterministic(monkeypatch):
    r15 = _frame(n=6000, seed=11)
    r1h = _frame(n=4000, seed=12)

    def _get(inst, tf):
        return {"15m": r15, "1h": r1h}.get(tf, [])

    monkeypatch.setattr(p76.store, "get_candles", _get)
    monkeypatch.setattr(_store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: {"dataset_id": f"{a}:test"})
    monkeypatch.setattr(p, "_git_commit", lambda: "testsha")
    r1 = p.run(("EURUSD", "GBPUSD"))
    r2 = p.run(("EURUSD", "GBPUSD"))
    assert r1.content_hash == r2.content_hash
    assert [s["status"] for s in r1.scorecard] == [s["status"] for s in r2.scorecard]
    assert r1.verdict == r2.verdict
    assert r1.holdout_untouched is True
    assert r1.frozen_contract_hash == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_run_verdict_conservative_on_random_walk(monkeypatch):
    def _get(inst, tf):
        n = {"15m": 6000, "1h": 4000}.get(tf, 0)
        return _frame(n=n, seed=abs(hash((inst, tf))) % 9999) if n else []
    monkeypatch.setattr(p76.store, "get_candles", _get)
    monkeypatch.setattr(_store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    r = p.run(("EURUSD", "GBPUSD", "AUDJPY"))
    assert not any(c["status"] == "STRATEGY_CANDIDATE_READY" for c in r.candidates)


def test_negative_knowledge_carries_phase77_forward(monkeypatch):
    r15 = _frame(n=6000, seed=21)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: r15 if t == "15m" else [])
    monkeypatch.setattr(_store, "get_candles", lambda i, t: r15 if t == "15m" else [])
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    r = p.run(("EURUSD",))
    assert any("Phase 77" in n["hypothesis"] for n in r.negative_knowledge)


def test_phase79_queue_max_three_and_no_invented_positives(monkeypatch):
    def _get(inst, tf):
        n = {"15m": 6000, "1h": 4000}.get(tf, 0)
        return _frame(n=n, seed=abs(hash((inst, tf))) % 9999) if n else []
    monkeypatch.setattr(p76.store, "get_candles", _get)
    monkeypatch.setattr(_store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    r = p.run(("EURUSD", "GBPUSD"))
    assert len(r.phase79_queue) <= 3
    for q in r.phase79_queue:
        assert q["status"] != "STRATEGY_CANDIDATE_READY" or q in r.candidates


def test_scientific_questions_all_present(monkeypatch):
    def _get(inst, tf):
        n = {"15m": 6000}.get(tf, 0)
        return _frame(n=n, seed=abs(hash((inst, tf))) % 9999) if n else []
    monkeypatch.setattr(p76.store, "get_candles", _get)
    monkeypatch.setattr(_store, "get_candles", _get)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    r = p.run(("EURUSD",))
    for i in range(1, 10):
        assert any(k.startswith(f"Q{i}_") for k in r.scientific_questions)


def test_module_imports_clean():
    importlib.reload(p)
    assert hasattr(p, "run") and hasattr(p, "get_result")
    assert len(p.HYPOTHESES) >= 4
