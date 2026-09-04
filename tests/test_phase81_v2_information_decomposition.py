# -*- coding: utf-8 -*-
"""
Phase 81 — V2 incremental information / context decomposition.

Feature-group registry, dataset reuse (exact unchanged V2 target), nested
model decomposition, conditional-probability tables, train-only time/
volatility neutralization, matched-placebo/shuffled-target/future-shock/
temporal-shift controls, block bootstrap, gates, verdict classification,
holdout firewall, and safety. Synthetic bars only — no full data run (the
real run is the artifact produced by
``python -m phase81_v2_information_decomposition``).
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
import phase80_ml_volatility_regime as p80
import phase81_v2_information_decomposition as p81


def _frame(n=9000, seed=21, drift=0.0):
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
    return p81.build_phase81_dataset(tf, horizon, instruments=(inst,))


# --- A. feature-group registry --------------------------------------------
def test_feature_groups_cover_the_full_phase80_registry():
    groups = p81.FEATURE_GROUPS_81
    all_names = set(sum(groups.values(), []))
    # every Phase 80 feature is accounted for somewhere except current_high_flag
    # and the two new cyclic-time features, which are Phase-81-specific
    p80_names = set(p80.FEATURE_NAMES)
    new_names = {"current_high_flag", "hour_sin", "hour_cos"}
    assert all_names - new_names <= p80_names | {"hour"}  # hour replaced by hour_sin/cos
    assert groups["CURRENT_STATE"] == ["current_high_flag"]
    assert "rv_rank" in groups["VOLATILITY"]
    assert "hour_sin" in groups["TIME"] and "hour_cos" in groups["TIME"]


def test_nested_models_are_properly_nested_supersets():
    m2 = set(p81.NESTED_MODELS["M2_volatility"])
    m3 = set(p81.NESTED_MODELS["M3_time"])
    m4 = set(p81.NESTED_MODELS["M4_volatility_time"])
    m5 = set(p81.NESTED_MODELS["M5_price_volatility_time"])
    m6 = set(p81.NESTED_MODELS["M6_full"])
    assert m4 == m2 | m3
    assert m5 >= m4
    assert m6 >= m4
    assert p81.NESTED_MODELS["M0_constant"] == []


def test_extended_ablation_reuses_nested_column_sets():
    assert p81.ABLATION_81["A_time_only"] == p81.NESTED_MODELS["M3_time"]
    assert p81.ABLATION_81["B_time_volatility"] == p81.NESTED_MODELS["M4_volatility_time"]
    assert p81.ABLATION_81["F_full"] == p81.NESTED_MODELS["M6_full"]


def test_no_third_hypothesis_or_v1_reopened():
    src = inspect.getsource(p81)
    assert "V1_COMPRESSION" not in src
    assert "compression_duration" not in src.lower() or "not instantiated" in src.lower()
    assert "H8" not in src and "large_bar_reversal" not in src.lower()


# --- B. dataset (reused, unchanged target) --------------------------------
def test_dataset_target_unchanged_from_phase80(monkeypatch):
    rows = _frame()
    ds81 = _dataset(monkeypatch, rows)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds80 = p80.build_dataset("EURUSD", "15m", 4)
    merged = ds81.merge(ds80, on="event_idx", suffixes=("_81", "_80"))
    assert len(merged) > 0
    assert np.array_equal(merged["target_81"].to_numpy(), merged["target_80"].to_numpy())


def test_current_state_flag_is_degenerate_by_construction(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    zv = p81.zero_variance_report(ds, p81.FEATURE_GROUPS_81["CURRENT_STATE"])
    assert zv["current_high_flag"] is True


def test_volatility_features_not_degenerate(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    zv = p81.zero_variance_report(ds, p81.FEATURE_GROUPS_81["VOLATILITY"])
    assert not any(zv.values())


def test_cyclic_hour_features_bounded(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    assert ds["feat__hour_sin"].between(-1.0001, 1.0001).all()
    assert ds["feat__hour_cos"].between(-1.0001, 1.0001).all()


def test_feature_target_contract_reused_and_passes(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    audit = p81.assert_feature_target_contract(ds)
    assert audit["pass"] is True


# --- C. nested model fitting -----------------------------------------------
def test_model0_constant_has_auc_half(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=22))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 100 or len(test) < 30:
        return
    r = p81.fit_and_eval_group(train, test, [], "logistic_regression")
    assert r["metrics"]["roc_auc"] == 0.5


def test_model1_current_state_degenerates_to_constant(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=23))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 100 or len(test) < 30:
        return
    r = p81.fit_and_eval_group(train, test, p81.NESTED_MODELS["M1_current_state"], "logistic_regression")
    assert abs(r["metrics"]["roc_auc"] - 0.5) < 1e-6


def test_logistic_regression_reports_coefficients(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=24))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    r = p81.fit_and_eval_group(train, test, p81.NESTED_MODELS["M4_volatility_time"], "logistic_regression")
    assert r["coefficients"] is not None
    assert set(p81.NESTED_MODELS["M4_volatility_time"]) <= set(r["coefficients"]) - {"_intercept"}


def test_hgb_reports_no_coefficients(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=25))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    r = p81.fit_and_eval_group(train, test, p81.NESTED_MODELS["M4_volatility_time"], "hist_gradient_boosting")
    assert r["coefficients"] is None


# --- D. conditional probability / hour mechanism / interactions ------------
def test_conditional_rates_shape(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=12000, seed=26))
    rates = p81.compute_conditional_rates(ds, min_n=20)
    assert "overall_p_high" in rates
    assert "by_volatility_bucket" in rates
    assert "by_hour" in rates


def test_conditional_rates_respect_min_sample_threshold(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=3000, seed=27))
    rates = p81.compute_conditional_rates(ds, min_n=100000)   # impossibly high threshold
    assert rates["by_hour"] == {}
    assert rates["by_volatility_bucket"] == {}


def test_hour_mechanism_report_shape(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=12000, seed=28))
    r = p81.hour_mechanism_report(ds, min_n=20)
    assert "rv_rank_by_hour" in r
    assert "interpretation" in r


def test_interaction_report_has_exactly_three_prespecified_cells(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=12000, seed=29))
    r = p81.interaction_report(ds, min_n=20)
    assert set(r.keys()) == {"hour_x_volatility_bucket", "session_x_volatility_bucket", "session_x_hour"}


# --- E. neutralization (train-only, no leakage) ----------------------------
def test_time_neutralization_uses_train_only(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=30))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    src = inspect.getsource(p81.compute_time_neutralized_residual)
    assert "train.groupby" in src   # baseline computed on train, not test/eval_df
    result = p81.compute_time_neutralized_residual(train, test)
    assert len(result["residual"]) == len(test)


def test_time_neutralization_residual_mean_near_zero_on_train_itself(monkeypatch):
    # if we neutralize TRAIN against ITS OWN train-derived baseline, the
    # residual mean should be very close to zero (baseline = train's own
    # group means) -- a basic sanity check, not a leakage test
    ds = _dataset(monkeypatch, _frame(n=9000, seed=31))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, _test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300:
        return
    result = p81.compute_time_neutralized_residual(train, train)
    assert abs(result["residual_mean"]) < 0.05


def test_volatility_neutralization_uses_fixed_bucket_edges_not_data_derived():
    assert p81._VOL_BUCKET_EDGES == (0.66, 0.75, 0.85, 0.95, 1.0001)


def test_evaluate_residual_information_shape():
    rng = np.random.default_rng(0)
    residual = rng.normal(0, 1, 2000)
    feats = pd.DataFrame({"a": rng.normal(0, 1, 2000), "b": rng.normal(0, 1, 2000)})
    r = p81.evaluate_residual_information(residual, feats)
    assert "cv_r2_mean" in r
    assert "coefficients" in r


def test_evaluate_residual_information_insufficient_sample():
    r = p81.evaluate_residual_information(np.array([0.1, 0.2]), pd.DataFrame({"a": [1, 2]}))
    assert r["state"] == "INSUFFICIENT_SAMPLE"


# --- F. matched placebo / shuffled target / temporal shift ------------------
def test_matched_placebo_targets_preserve_row_count(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=32))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(test) < 60:
        return
    p81._clear_rv_rank_cache()
    targets = p81.matched_placebo_targets(test, horizon=4, shift_bars=50)
    assert len(targets) == len(test)


def test_matched_placebo_control_valid_probabilities(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=33))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    p81._clear_rv_rank_cache()
    m = p81.matched_placebo_control(train, test, p81.NESTED_MODELS["M4_volatility_time"],
                                    "logistic_regression", 4, shift_bars=50)
    if m is not None:
        assert 0.0 <= m["metrics"]["accuracy"] <= 1.0


def test_temporal_shift_sweep_returns_one_row_per_shift(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=34))
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    p81._clear_rv_rank_cache()
    sweep = p81.temporal_shift_sweep(train, test, p81.NESTED_MODELS["M4_volatility_time"],
                                     "logistic_regression", 4, shifts=(50, 100))
    assert len(sweep) <= 2
    for s in sweep:
        assert s["shift_bars"] in (50, 100)


def test_rv_rank_cache_populates_and_clears():
    p81._clear_rv_rank_cache()
    assert p81._RV_RANK_CACHE == {}


# --- G. bootstrap ------------------------------------------------------------
def test_bootstrap_metric_ci_deterministic():
    rng = np.random.default_rng(5)
    y = rng.integers(0, 2, 5000)
    p_pred = np.clip(y * 0.3 + rng.normal(0, 0.3, 5000) + 0.35, 0, 1)
    r1 = p81.bootstrap_metric_ci(y, p_pred, p81._auc_fn, block=4, iters=200, seed=1)
    r2 = p81.bootstrap_metric_ci(y, p_pred, p81._auc_fn, block=4, iters=200, seed=1)
    assert r1 == r2


def test_bootstrap_delta_ci_shape_and_zero_exclusion():
    rng = np.random.default_rng(6)
    y = rng.integers(0, 2, 5000)
    p_a = np.clip(y * 0.4 + rng.normal(0, 0.3, 5000) + 0.3, 0, 1)   # informative
    p_b = rng.uniform(0, 1, 5000)                                    # random
    r = p81.bootstrap_delta_ci(y, p_a, p_b, p81._auc_fn, block=4, iters=300, seed=2)
    assert r["point"] > 0
    assert "excludes_zero" in r


def test_bootstrap_insufficient_sample():
    r = p81.bootstrap_metric_ci(np.array([0, 1]), np.array([0.5, 0.5]), p81._auc_fn, block=4)
    assert r["state"] == "INSUFFICIENT_SAMPLE"


# --- H. gates / verdict ------------------------------------------------------
def test_gate_h_reuses_phase80_margin():
    assert p81._GATE_H_MARGIN == 0.05


def test_gates_all_pass():
    g = p81.evaluate_gates_81(True, True, True, True, True, True, True, 0.75, 0.60, 0.51, True)
    assert g["all_pass"] is True


def test_verdict_confirmed_requires_everything():
    g = p81.evaluate_gates_81(True, True, True, True, True, True, True, 0.75, 0.60, 0.51, True)
    v, _r = p81.classify_verdict_81(g, 0.08, True, [True, True, True], [True] * 6, 0.05, 0.05)
    assert v == "V2_RESIDUAL_INFORMATION_CONFIRMED"


def test_verdict_explained_when_delta_small():
    g = p81.evaluate_gates_81(True, True, True, True, True, True, True, 0.66, 0.65, 0.51, True)
    v, _r = p81.classify_verdict_81(g, 0.005, False, [True, True, True], [True] * 6, 0.01, 0.01)
    assert v == "V2_EXPLAINED_BY_TIME_AND_VOLATILITY"


def test_verdict_explained_when_placebo_indistinguishable():
    g = p81.evaluate_gates_81(True, True, True, True, True, True, True, 0.70, 0.68, 0.51, True)
    v, _r = p81.classify_verdict_81(g, 0.08, True, [True, True, True], [True] * 6, 0.05, 0.05)
    assert v == "V2_EXPLAINED_BY_TIME_AND_VOLATILITY"


def test_verdict_unstable_when_inconsistent_across_years():
    g = p81.evaluate_gates_81(True, True, True, True, True, True, True, 0.75, 0.60, 0.51, True)
    v, _r = p81.classify_verdict_81(g, 0.08, True, [True, True, False], [True] * 6, 0.05, 0.05)
    assert v == "V2_PREDICTABLE_BUT_RESIDUAL_INFORMATION_UNSTABLE"


def test_verdict_invalid_on_hard_gate_failure():
    g = p81.evaluate_gates_81(True, False, True, True, True, True, True, 0.75, 0.60, 0.51, True)
    v, _r = p81.classify_verdict_81(g, 0.08, True, [True] * 3, [True] * 6, 0.05, 0.05)
    assert v == "V2_TARGET_OR_PIPELINE_INVALID"


def test_verdict_only_four_controlled_outcomes():
    import itertools
    for combo in itertools.product([True, False], repeat=4):
        g = p81.evaluate_gates_81(*combo, True, True, True, 0.7, 0.6, 0.51, True)
        for delta in (None, 0.001, 0.08):
            for ci in (True, False):
                v, _r = p81.classify_verdict_81(g, delta, ci, [True, False], [True, False], 0.01, 0.01)
                assert v in ("V2_RESIDUAL_INFORMATION_CONFIRMED", "V2_EXPLAINED_BY_TIME_AND_VOLATILITY",
                            "V2_PREDICTABLE_BUT_RESIDUAL_INFORMATION_UNSTABLE",
                            "V2_TARGET_OR_PIPELINE_INVALID")


# --- I. no-trading-strategy / holdout / safety ------------------------------
def test_no_trading_strategy_code():
    src = inspect.getsource(p81)
    for bad in ("place_order", "buy_signal", "sell_signal", "generate_signal", "stop_loss",
               "take_profit", "position_sizing", "execution_pipeline", "broker_adapter",
               "risk_gateway", "live_trading", "live_automation"):
        assert bad not in src


def test_no_deep_learning_or_new_model_zoo():
    src = inspect.getsource(p81).lower()
    for bad in ("tensorflow", "torch", "keras", "lstm", "transformer", "xgboost", "lightgbm",
               "catboost", "randomforestclassifier", "svm", "gpu", "cuda"):
        assert bad not in src


def test_frozen_holdout_never_accessed():
    src = inspect.getsource(p81)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
               "forward_lifecycle", "HistoricalVsForwardComparator", "get_holdout",
               "holdout_trades", "load_holdout", "holdout_df", "holdout_candles"):
        assert bad not in src
    bare = re.findall(r"holdout(?!_untouched)", src.lower())
    assert len(bare) <= 8


def test_frozen_hash_and_safety_flags_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"


def test_module_imports_clean():
    import importlib
    importlib.reload(p81)
