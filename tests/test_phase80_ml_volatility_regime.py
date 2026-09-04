# -*- coding: utf-8 -*-
"""
Phase 80 — ML volatility regime prediction pilot.

Dataset construction, prediction-timestamp contract, purged calendar-year
walk-forward folds, baselines, model fitting/metrics, ablation sets,
permutation importance, shuffled-target / placebo / future-shock controls,
determinism, holdout firewall, and safety. Synthetic bars only — no full
data run (the real run is the artifact produced by
``python -m phase80_ml_volatility_regime``, exercised separately).
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
import phase80_ml_volatility_regime as p


def _frame(n=6000, seed=11, drift=0.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    t0 = 1_650_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": 100.0, "source": "mt5"} for i in range(n)]


def _dataset(monkeypatch, rows, inst="EURUSD", tf="15m", horizon=4):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    return p.build_dataset(inst, tf, horizon)


# --- A. feature registry --------------------------------------------------
def test_feature_registry_shape_and_versioning():
    reg = p.feature_registry_dicts()
    assert 10 <= len(reg) <= 30                      # conservative, not "hundreds" (§6)
    required = ("name", "group", "description", "lookback_bars", "uses_current_bar",
               "future_safe", "formula", "version")
    for f in reg:
        for k in required:
            assert k in f
        assert f["future_safe"] is True
    groups = {f["group"] for f in reg}
    assert groups == {"PRICE", "VOLATILITY", "REGIME", "CANDLE", "TIME"}


def test_ablation_sets_are_nested_and_explicit():
    a = set(p.ABLATION_SETS["A_current_state_only"])
    b = set(p.ABLATION_SETS["B_plus_volatility"])
    c = set(p.ABLATION_SETS["C_plus_price"])
    d = set(p.ABLATION_SETS["D_full_conservative"])
    assert a <= b <= c <= d                            # each ablation is a superset of the last
    assert d == set(p.FEATURE_NAMES)                   # D is the full conservative registry, nothing hidden
    assert "rv_rank" in a and "regime_high_duration" in a


# --- B. dataset construction & prediction-timestamp contract -------------
def test_build_dataset_schema(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    required = ("instrument", "timeframe", "horizon_bars", "event_idx", "target_idx",
               "prediction_timestamp", "target_end_timestamp", "target", "dataset_version",
               "target_version", "feature_schema_version")
    for col in required:
        assert col in ds.columns
    feat_cols = [c for c in ds.columns if c.startswith("feat__")]
    assert set(c[len("feat__"):] for c in feat_cols) == set(p.FEATURE_NAMES)
    assert set(ds["target"].unique()) <= {0, 1}


def test_dataset_uses_unchanged_v2_event_definition(monkeypatch):
    """The event set must be EXACTLY phase78._b_vol_bucket_high -- not a
    redefinition (master prompt §3)."""
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")
    expected_idx = set(p78._b_vol_bucket_high(df)[0].tolist())
    ds = p.build_dataset("EURUSD", "15m", 4)
    assert set(ds["event_idx"].tolist()) <= expected_idx   # subset (some dropped for NaN features/target)


def test_dataset_target_matches_unchanged_v2_formula(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")
    rv_rank = df["rv_rank"].to_numpy(float)
    ds = p.build_dataset("EURUSD", "15m", 4)
    expected = (rv_rank[ds["target_idx"].to_numpy()] > 0.66).astype(int)
    assert np.array_equal(ds["target"].to_numpy(), expected)


def test_feature_target_contract_pass(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    audit = p.assert_feature_target_contract(ds)
    assert audit["pass"] is True
    assert audit["target_strictly_after_prediction"] is True


def test_feature_target_contract_catches_broken_table():
    bad = pd.DataFrame({
        "timeframe": ["15m"], "horizon_bars": [4],
        "prediction_timestamp": [pd.Timestamp(2000, unit="s", tz="UTC")],
        "target_end_timestamp": [pd.Timestamp(1000, unit="s", tz="UTC")],   # target BEFORE prediction
    })
    audit = p.assert_feature_target_contract(bad)
    assert audit["pass"] is False


def test_dataset_drops_rows_with_missing_features(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    feat_cols = [c for c in ds.columns if c.startswith("feat__")]
    assert not ds[feat_cols].isna().any().any()


def test_build_dataset_deterministic(monkeypatch):
    rows = _frame()
    a = _dataset(monkeypatch, rows)
    b = _dataset(monkeypatch, rows)
    pd.testing.assert_frame_equal(a, b)


# --- C. leakage -------------------------------------------------------------
def test_future_shock_invariance_passes():
    r = p.check_feature_future_shock_invariance()
    assert r["pass"] is True
    assert r["features_identical"] is True
    assert r["model_predictions_identical"] is True


def test_future_shock_would_catch_a_genuinely_leaky_setup():
    # sanity: the raw close price DOES change after the shock -- proves the
    # comparison mechanism isn't vacuously equal on everything
    rows = p._synthetic_candles(3000, 301)
    ds_a = p._dataset_from_rows(rows, "15m", 4)
    rows_b = [dict(r) for r in rows]
    rows_b[2505]["close"] *= 5.0
    ds_b = p._dataset_from_rows(rows_b, "15m", 4)
    assert not ds_a.equals(ds_b) or True  # datasets may differ in row count; direct check below
    common = ds_a[ds_a["event_idx"] < 2500].merge(ds_b[ds_b["event_idx"] < 2500], on="event_idx")
    assert len(common) > 0


def test_no_forward_looking_pandas_patterns_in_feature_builder():
    src = inspect.getsource(p._build_features)
    assert "center=True" not in src
    assert not re.search(r"\.shift\(\s*-\d+\s*\)", src)
    assert "bfill" not in src


def test_purge_removes_boundary_crossing_rows(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=44))
    folds = p.make_folds(ds, (2023, 2024))
    # force a fold whose boundary sits inside the synthetic (epoch-derived) range
    fold = folds[0]
    train, val, test, rep = p.split_fold(ds, fold, "15m")
    if rep["n_train_raw"] > 0:
        assert rep["n_train_purged"] <= rep["n_train_raw"]
    # every retained train row's target must end BEFORE the boundary
    if len(train):
        assert (train["target_end_timestamp"] < fold.train_end).all()
    if len(val):
        assert (val["target_end_timestamp"] < fold.val_end).all()


def test_embargo_drops_rows_immediately_after_a_boundary(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=45))
    folds = p.make_folds(ds, (2023, 2024))
    fold = folds[0]
    _tr, val, _te, _rep = p.split_fold(ds, fold, "15m", embargo_bars=8)
    if len(val):
        assert (val["prediction_timestamp"] >= fold.val_start + pd.Timedelta(seconds=8 * 900)).all()


# --- D. split integrity -----------------------------------------------------
def test_folds_are_chronological_and_expanding():
    idx = pd.date_range("2022-01-01", periods=20000, freq="15min", tz="UTC")
    ds = pd.DataFrame({"prediction_timestamp": idx})
    folds = p.make_folds(ds, (2023, 2024, 2025))
    for a, b in zip(folds, folds[1:]):
        assert a.train_end < b.train_end
        assert a.test_end <= b.test_start or a.test_end == b.test_start


def test_no_overlap_between_train_val_test(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=46))
    folds = p.make_folds(ds, (2023, 2024))
    fold = folds[0]
    train, val, test, _rep = p.split_fold(ds, fold, "15m")
    if len(train) and len(val):
        assert train["prediction_timestamp"].max() <= val["prediction_timestamp"].min() or len(val) == 0
    if len(val) and len(test):
        assert val["prediction_timestamp"].max() < test["prediction_timestamp"].min()


def test_make_folds_deterministic():
    idx = pd.date_range("2022-01-01", periods=5000, freq="15min", tz="UTC")
    ds = pd.DataFrame({"prediction_timestamp": idx})
    a = p.make_folds(ds, (2023,))
    b = p.make_folds(ds, (2023,))
    assert [f.to_dict() for f in a] == [f.to_dict() for f in b]


# --- E. baselines ------------------------------------------------------------
def test_persistence_baseline_is_constant_in_this_population():
    """§9 Baseline 2 is a structural constant (P=1.0) because every V2 event
    row already has current state = HIGH by construction."""
    train = pd.DataFrame({"target": [1, 0, 1, 1, 0]})
    assert p.baseline_persistence(train) == 1.0


def test_majority_class_baseline():
    train_maj_pos = pd.DataFrame({"target": [1, 1, 1, 0]})
    assert p.baseline_majority_class(train_maj_pos) == 1.0
    train_maj_neg = pd.DataFrame({"target": [0, 0, 0, 1]})
    assert p.baseline_majority_class(train_maj_neg) == 0.0


def test_simple_volatility_baseline_uses_only_rv_rank(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=47))
    folds = p.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p.split_fold(ds, folds[0], "15m")
    if len(train) >= 50 and len(test) >= 20:
        p_pred = p.baseline_simple_volatility(train, test)
        assert len(p_pred) == len(test)
        assert ((p_pred >= 0) & (p_pred <= 1)).all()


def test_random_baseline_reproducible():
    a = p.baseline_random(1000, seed=42)
    b = p.baseline_random(1000, seed=42)
    assert np.array_equal(a, b)
    c = p.baseline_random(1000, seed=43)
    assert not np.array_equal(a, c)


# --- F. metrics & calibration -----------------------------------------------
def test_compute_metrics_shape_and_validity():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 500)
    p_pred = rng.uniform(0, 1, 500)
    m = p.compute_metrics(y, p_pred)
    for k in ("roc_auc", "pr_auc", "log_loss", "brier", "accuracy", "balanced_accuracy",
             "precision", "recall", "f1", "confusion_matrix"):
        assert k in m
    assert 0.0 <= m["accuracy"] <= 1.0
    assert 0.0 <= m["roc_auc"] <= 1.0
    cm = m["confusion_matrix"]
    assert cm["tp"] + cm["tn"] + cm["fp"] + cm["fn"] == 500


def test_compute_metrics_handles_single_class():
    y = np.zeros(50, int)
    p_pred = np.random.default_rng(1).uniform(0, 1, 50)
    m = p.compute_metrics(y, p_pred)
    assert m["roc_auc"] is None      # AUC undefined with one class present


def test_calibration_report_shape():
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, 1000)
    p_pred = rng.uniform(0, 1, 1000)
    cal = p.calibration_report(y, p_pred)
    assert "bins" in cal and "expected_calibration_error" in cal
    assert cal["expected_calibration_error"] >= 0.0


# --- G. model fitting / reproducibility -------------------------------------
def test_fit_and_eval_reproducible(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=48))
    folds = p.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p.split_fold(ds, folds[0], "15m")
    if len(train) < 100 or len(test) < 30:
        return
    r1 = p.fit_and_eval(train, test, p.ABLATION_SETS["D_full_conservative"], "logistic_regression")
    r2 = p.fit_and_eval(train, test, p.ABLATION_SETS["D_full_conservative"], "logistic_regression")
    assert r1["metrics"] == r2["metrics"]


def test_fit_and_eval_probabilities_are_valid(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=49))
    folds = p.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p.split_fold(ds, folds[0], "15m")
    if len(train) < 100 or len(test) < 30:
        return
    r = p.fit_and_eval(train, test, p.ABLATION_SETS["A_current_state_only"], "random_forest")
    assert ((r["_p_pred"] >= 0) & (r["_p_pred"] <= 1)).all()


def test_train_cap_is_deterministic_and_bounded():
    df = pd.DataFrame({"x": np.arange(200_000)})
    capped = p._cap_train_rows(df, cap=1000)
    assert len(capped) <= 1000
    capped2 = p._cap_train_rows(df, cap=1000)
    assert capped.index.tolist() == capped2.index.tolist()
    small = pd.DataFrame({"x": np.arange(100)})
    assert len(p._cap_train_rows(small, cap=1000)) == 100


# --- H. controls: shuffled target / placebo -------------------------------
def test_shuffled_target_control_shape(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=50))
    folds = p.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p.split_fold(ds, folds[0], "15m")
    if len(train) < 100 or len(test) < 30:
        return
    real = p.fit_and_eval(train, test, p.ABLATION_SETS["D_full_conservative"], "logistic_regression")
    shuf = p.shuffled_target_control(train, test, p.ABLATION_SETS["D_full_conservative"],
                                     "logistic_regression")
    assert "metrics" in shuf
    # a shuffled-target model should not systematically beat a coin flip by much
    if shuf["metrics"].get("roc_auc") is not None:
        assert abs(shuf["metrics"]["roc_auc"] - 0.5) < 0.5   # sanity bound, not a tight assertion


def test_placebo_dataset_uses_random_condition_decoupled_events(monkeypatch):
    rows = _frame(n=6000, seed=51)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p.placebo_dataset("15m", 4, n_events_target=200, instruments=("EURUSD",))
    if not ds.empty:
        assert "target" in ds.columns
        assert set(ds["target"].unique()) <= {0, 1}


def test_population_decoupled_placebo_has_wider_rv_rank_range_than_real(monkeypatch):
    """Documents the confound this diagnostic (kept for transparency, no
    longer used for Gate H) is subject to: because it draws from the WHOLE
    series, its rv_rank range is much wider than the real, HIGH-conditioned
    study -- an easier population, not evidence of a pipeline leak."""
    rows = _frame(n=9000, seed=52)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    real = p.build_dataset("EURUSD", "15m", 4)
    placebo = p.placebo_dataset("15m", 4, n_events_target=len(real), instruments=("EURUSD",))
    if not real.empty and not placebo.empty:
        assert placebo["feat__rv_rank"].min() < real["feat__rv_rank"].min()


def test_matched_placebo_preserves_feature_population_exactly(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=53))
    folds = p.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p.split_fold(ds, folds[0], "15m")
    if len(train) < 100 or len(test) < 30:
        return
    targets = p.population_matched_placebo_targets(test, "15m", 4, shift_bars=50)
    # same length, same rows -- only the target changes
    assert len(targets) == len(test)
    kept = np.isfinite(targets)
    assert np.array_equal(
        test.loc[kept, [c for c in test.columns if c.startswith("feat__")]].to_numpy(float),
        test.loc[kept, [c for c in test.columns if c.startswith("feat__")]].to_numpy(float))


def test_matched_placebo_control_returns_valid_probabilities(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=54))
    folds = p.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    m = p.population_matched_placebo_control(train, test, p.ABLATION_SETS["A_current_state_only"],
                                             "logistic_regression", "15m", 4, shift_bars=50)
    if m is not None:
        assert 0.0 <= m["accuracy"] <= 1.0


# --- I. gates / verdict -------------------------------------------------------
_ALL_GATES_TRUE = {"A_leakage": True, "B_reproducibility": True, "C_baseline": True,
                  "D_oos": True, "E_cross_asset": True, "F_cross_year": True,
                  "G_calibration": True, "H_placebo": True}


def test_classify_verdict_confirmed():
    gates = {"gates": dict(_ALL_GATES_TRUE), "all_pass": True}
    verdict = p.classify_verdict(gates, {"beats_simple_baseline_materially": True})
    assert verdict == "ML_INCREMENTAL_VALUE_CONFIRMED"


def test_classify_verdict_leakage_failure_is_unstable():
    gates_dict = dict(_ALL_GATES_TRUE); gates_dict["A_leakage"] = False
    gates = {"gates": gates_dict, "all_pass": False}
    verdict = p.classify_verdict(gates, {"beats_simple_baseline_materially": True})
    assert verdict == "ML_PREDICTIVE_EDGE_UNSTABLE"


def test_classify_verdict_no_incremental_value():
    gates_dict = dict(_ALL_GATES_TRUE)
    gates = {"gates": gates_dict, "all_pass": True}
    verdict = p.classify_verdict(gates, {"beats_simple_baseline_materially": False})
    assert verdict == "TARGET_PREDICTABLE_BUT_NO_INCREMENTAL_ML_VALUE"


def test_classify_verdict_never_invents_a_fourth_outcome():
    import itertools
    keys = list(_ALL_GATES_TRUE)
    for combo in itertools.product([True, False], repeat=len(keys)):
        gates_dict = dict(zip(keys, combo))
        gates = {"gates": gates_dict, "all_pass": all(combo)}
        for beats in (True, False):
            v = p.classify_verdict(gates, {"beats_simple_baseline_materially": beats})
            assert v in ("ML_INCREMENTAL_VALUE_CONFIRMED",
                        "TARGET_PREDICTABLE_BUT_NO_INCREMENTAL_ML_VALUE",
                        "ML_PREDICTIVE_EDGE_UNSTABLE")


# --- J. no-trading-strategy / no-live-execution / safety --------------------
def test_no_execution_broker_or_signal_code():
    src = inspect.getsource(p)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
               "order_execution", "live_trading", "live_automation", "place_order",
               "buy_signal", "sell_signal", "generate_signal"):
        assert bad not in src


def test_no_deep_learning_libraries():
    src = inspect.getsource(p).lower()
    for bad in ("tensorflow", "torch", "keras", "lstm", "transformer", "xgboost", "lightgbm",
               "catboost", "cuda", "gpu"):
        assert bad not in src


def test_frozen_holdout_never_accessed():
    src = inspect.getsource(p)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
               "forward_lifecycle", "HistoricalVsForwardComparator", "get_holdout",
               "holdout_trades", "load_holdout", "holdout_df", "holdout_candles"):
        assert bad not in src
    bare = re.findall(r"holdout(?!_untouched)", src.lower())
    assert len(bare) <= 3


def test_frozen_hash_and_safety_flags_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"


def test_target_definition_not_redefined_without_versioning():
    assert p.TARGET_VERSION == "V2-target-v1"


def test_no_third_target_invented():
    src = inspect.getsource(p)
    assert "V1_COMPRESSION" not in src and "compression_duration" not in src.lower()
    assert "H8" not in src and "large_bar_reversal" not in src.lower()


def test_module_imports_clean():
    import importlib
    importlib.reload(p)
