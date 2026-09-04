# -*- coding: utf-8 -*-
"""
Phase 82 — V1 15m compression -> expansion ML pilot.

Canonical V1 definition reuse, the documented duration-degeneracy /
extended-population resolution, per-row target reproduction of Phase 78's
own aggregate numbers, the future-shock-driven raw-vs-baseline-centred
target correction, feature-group registry, nested regression decomposition,
duration dose-response, severity decorrelation, train-only residualization,
matched-placebo/shuffled-target/future-shock/temporal-shift controls, gates,
verdict classification, holdout firewall, and safety. Synthetic bars only —
no full data run (the real run is the artifact produced by
``python -m phase82_compression_expansion_ml_pilot``).
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
import phase80_ml_volatility_regime as p80
import phase82_compression_expansion_ml_pilot as p82


def _frame(n=9000, seed=41, drift=0.0):
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


def _dataset(monkeypatch, rows, inst="EURUSD", canonical=False, horizon=4):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    return (p82.build_canonical_v1_dataset if canonical else p82.build_v1_dataset)(inst, "15m", horizon)


# --- A. canonical definition reuse / ambiguity resolution ------------------
def test_canonical_event_is_unchanged_phase78_builder(monkeypatch):
    rows = _frame(n=9000, seed=42)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")
    expected = set(p78._b_compression_duration(df)[0].tolist())
    got = set(p82.canonical_event_indices(df).tolist())
    assert got == expected


def test_canonical_duration_is_degenerate(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=43), canonical=True)
    if ds.empty:
        return
    assert set(ds["feat__duration"].unique().tolist()) == {3.0}


def test_extended_duration_is_variable(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=44), canonical=False)
    if ds.empty:
        return
    assert ds["feat__duration"].nunique() > 1
    assert ds["feat__duration"].min() == 3.0


def test_extended_population_is_superset_of_canonical(monkeypatch):
    rows = _frame(n=9000, seed=45)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")
    canon = set(p82.canonical_event_indices(df).tolist())
    ext = set(p82.extended_event_indices(df).tolist())
    assert canon <= ext


def test_per_row_target_reproduces_phase78_aggregate_exactly(monkeypatch):
    rows = _frame(n=9000, seed=46)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")
    idx0 = p78._b_compression_duration(df)[0]
    res = p78.study_range_expansion(df, idx0, horizons=(4,))
    if res["state"] != "OK":
        return
    ds = p82.build_canonical_v1_dataset("EURUSD", "15m", 4)
    # raw target minus stored baseline_mean must equal Phase78's centred mean
    centred_mean = float((ds["target"] - ds["baseline_mean"]).mean())
    assert abs(centred_mean - res["horizons"]["h4"]["mean"]) < 1e-6


def test_raw_target_is_not_baseline_centred(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=47), canonical=True)
    if ds.empty:
        return
    # the raw target should differ from a hypothetical centred version
    # whenever baseline_mean is nonzero
    if abs(ds["baseline_mean"].iloc[0]) > 1e-9:
        assert not np.allclose(ds["target"].to_numpy(), (ds["target"] - ds["baseline_mean"]).to_numpy())


# --- B. feature groups / nested models --------------------------------------
def test_feature_groups_shape():
    groups = p82.FEATURE_GROUPS_82
    assert set(groups) == {"COMPRESSION", "VOLATILITY", "RANGE_PRICE", "TIME", "REGIME"}
    assert groups["COMPRESSION"] == ["duration", "severity"]


def test_nested_models_nested_supersets():
    m1, m2, m3 = (set(p82.NESTED_MODELS_82[k]) for k in
                 ("M1_volatility", "M2_compression", "M3_compression_volatility"))
    assert m3 == m1 | m2
    m5, m6 = set(p82.NESTED_MODELS_82["M5_volatility_time"]), set(p82.NESTED_MODELS_82["M6_compression_volatility_time"])
    assert m6 == m5 | m2
    assert p82.NESTED_MODELS_82["M0_constant"] == []
    assert set(p82.NESTED_MODELS_82["M8_full"]) >= m6


def test_extended_ablation_reuses_nested_sets():
    assert p82.ABLATION_82["D_volatility_time"] == p82.NESTED_MODELS_82["M5_volatility_time"]
    assert p82.ABLATION_82["F_compression_volatility_time"] == p82.NESTED_MODELS_82["M6_compression_volatility_time"]


def test_no_v2_reopened():
    src = inspect.getsource(p82)
    assert "rv_rank > 0.66" not in src.replace(" ", "")
    assert "V2_HIGH_VOL" not in src


# --- C. dataset / contract ---------------------------------------------------
def test_dataset_schema(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=48))
    for col in ("instrument", "timeframe", "horizon_bars", "event_idx", "target_idx",
               "prediction_timestamp", "target_end_timestamp", "target", "baseline_mean",
               "dataset_version", "target_version"):
        assert col in ds.columns


def test_feature_target_contract_passes(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=49))
    if ds.empty:
        return
    audit = p82.assert_feature_target_contract(ds)
    assert audit["pass"] is True


def test_severity_transform_sign(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=50))
    if ds.empty:
        return
    # severity = threshold - atr_rank, so it must be >= 0 for every compressed event
    assert (ds["feat__severity"] >= -1e-9).all()


# --- D. leakage / event-selection / censoring / overlap audits -------------
def test_event_selection_audit_passes(monkeypatch):
    rows = _frame(n=9000, seed=51)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")
    audit = p82.event_selection_audit(df, p82.extended_event_indices)
    assert audit["identical"] is True


def test_event_selection_audit_would_catch_a_forward_looking_builder(monkeypatch):
    rows = _frame(n=9000, seed=52)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")

    def _bad_event_fn(d):
        # deliberately peeks far enough into the future (beyond the audit's
        # own 10-bar boundary buffer) to prove the detector works
        fut = d["close"].shift(-30)
        idx = np.where(np.isfinite(fut) & (fut > d["close"]))[0]
        return idx[idx >= 200]

    audit = p82.event_selection_audit(df, _bad_event_fn)
    assert audit["identical"] is False


def test_censored_event_audit_shape(monkeypatch):
    rows = _frame(n=9000, seed=53)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")
    audit = p82.censored_event_audit(df, p82.extended_event_indices, 4)
    assert audit["n_censored_dropped"] >= 0
    assert audit["n_events_before_censor_check"] >= audit["n_censored_dropped"]


def test_event_overlap_extended_is_heavier_than_canonical(monkeypatch):
    rows = _frame(n=9000, seed=54)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    df = p78.augment(p76.load_bars("EURUSD", "15m"), "15m")
    ext = p82.event_overlap_audit(p82.extended_event_indices(df), 4)
    canon = p82.event_overlap_audit(p82.canonical_event_indices(df), 4)
    if ext.get("n_events", 0) > 5 and canon.get("n_events", 0) > 5:
        assert ext["pct_neighboring_pairs_overlapping"] >= canon["pct_neighboring_pairs_overlapping"]


def test_future_shock_invariance_passes():
    r = p82.check_future_shock_invariance()
    assert r["pass"] is True
    assert r["features_identical"] is True
    assert r["targets_identical_before_cutoff"] is True
    assert r["model_predictions_identical"] is True


# --- E. duration statistics / dose-response ---------------------------------
def test_duration_statistics_shape(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=55))
    if ds.empty:
        return
    stats = p82.compute_duration_statistics(ds)
    assert stats["min"] == 3.0
    assert "distribution" in stats


def test_duration_dose_response_predeclared_bins(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=56))
    if ds.empty:
        return
    dr = p82.compute_duration_dose_response(ds, min_n=5)
    for label in dr["by_duration_bucket"]:
        assert label in p82._DURATION_BIN_LABELS


def test_duration_severity_decorrelation_shape(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=57))
    if ds.empty:
        return
    r = p82.duration_severity_decorrelation(ds)
    assert "pearson_corr_duration_severity" in r


# --- F. residualization (train-only) ----------------------------------------
def test_residualization_uses_train_only(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=58))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    src = inspect.getsource(p82.compute_context_residual)
    assert "train[" in src or "model.fit(train" in src.replace(" ", "")
    resid = p82.compute_context_residual(train, test, p82.FEATURE_GROUPS_82["VOLATILITY"])
    assert len(resid["residual"]) == len(test)


def test_evaluate_residual_information_insufficient_sample():
    r = p82.evaluate_residual_information(np.array([0.1, 0.2]), pd.DataFrame({"a": [1, 2]}))
    assert r["state"] == "INSUFFICIENT_SAMPLE"


# --- G. models / metrics -----------------------------------------------------
def test_constant_model_r2_zero(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=59))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 100 or len(test) < 30:
        return
    r = p82.fit_and_eval_82(train, test, [], "ridge")
    assert r["metrics"]["oos_r2"] == 0.0


def test_ridge_reports_coefficients(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=60))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    r = p82.fit_and_eval_82(train, test, p82.NESTED_MODELS_82["M5_volatility_time"], "ridge")
    assert r["coefficients"] is not None


def test_regression_metrics_shape():
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, 500)
    p = y * 0.3 + rng.normal(0, 0.9, 500)
    m = p82.compute_regression_metrics(y, p, float(np.mean(y)))
    for k in ("oos_r2", "mae", "rmse", "spearman"):
        assert k in m


def test_error_by_prediction_decile_shape():
    rng = np.random.default_rng(1)
    y = rng.normal(0, 1, 1000)
    p = y * 0.5 + rng.normal(0, 0.5, 1000)
    rows = p82.error_by_prediction_decile(y, p)
    assert len(rows) <= 10
    assert all("mean_predicted" in r and "mean_actual" in r for r in rows)


# --- H. controls -------------------------------------------------------------
def test_shuffled_target_control_near_chance(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=61))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    r = p82.shuffled_target_control(train, test, p82.NESTED_MODELS_82["M6_compression_volatility_time"], "ridge")
    assert abs(r["metrics"]["oos_r2"]) < 0.15   # sanity bound, not a tight assertion


def test_matched_placebo_targets_preserve_row_count(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=62))
    if ds.empty:
        return
    p82._clear_bar_cache_82()
    targets = p82.matched_placebo_targets(ds, horizon=4, shift_bars=50)
    assert len(targets) == len(ds)


def test_temporal_shift_sweep_shape(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=63))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 300 or len(test) < 60:
        return
    p82._clear_bar_cache_82()
    sweep = p82.temporal_shift_sweep(train, test, p82.NESTED_MODELS_82["M5_volatility_time"], "ridge", 4,
                                     shifts=(50, 100))
    assert len(sweep) <= 2


# --- I. gates / verdict -------------------------------------------------------
_ALL_TRUE = {"A_dataset_integrity": True, "B_leakage": True, "C_reproducibility": True,
            "D_residualization_methodology": True, "E_event_selection_valid": True,
            "F_cross_asset_complete": True, "G_cross_year_complete": True,
            "H_matched_placebo": True, "I_shuffled_target": True, "J_holdout_protected": True}


def test_gates_all_pass_shape():
    g = p82.evaluate_gates_82(True, True, True, True, True, True, True, 0.05, 0.02, 0.001, True)
    assert g["gates"]["H_matched_placebo"] is True


def test_verdict_confirmed():
    g = {"gates": dict(_ALL_TRUE), "all_pass": True}
    v, _r = p82.classify_verdict_82(g, 0.03, True, [True, True, True], [True] * 6)
    assert v == "V1_INCREMENTAL_INFORMATION_CONFIRMED"


def test_verdict_explained_by_context_when_delta_small():
    g = {"gates": dict(_ALL_TRUE), "all_pass": True}
    v, _r = p82.classify_verdict_82(g, 0.001, False, [True, True, True], [True] * 6)
    assert v == "V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT"


def test_verdict_explained_by_context_when_placebo_fails():
    checks = dict(_ALL_TRUE); checks["H_matched_placebo"] = False
    g = {"gates": checks, "all_pass": False}
    v, _r = p82.classify_verdict_82(g, 0.05, True, [True, True, True], [True] * 6)
    assert v == "V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT"


def test_verdict_unstable_when_year_inconsistent():
    g = {"gates": dict(_ALL_TRUE), "all_pass": True}
    v, _r = p82.classify_verdict_82(g, 0.05, True, [True, True, False], [True] * 6)
    assert v == "V1_SIGNAL_PRESENT_BUT_UNSTABLE"


def test_verdict_invalid_on_hard_gate_failure():
    checks = dict(_ALL_TRUE); checks["B_leakage"] = False
    g = {"gates": checks, "all_pass": False}
    v, _r = p82.classify_verdict_82(g, 0.05, True, [True] * 3, [True] * 6)
    assert v == "V1_TARGET_OR_PIPELINE_INVALID"


def test_verdict_only_four_controlled_outcomes():
    import itertools
    keys = list(_ALL_TRUE)
    for combo in itertools.product([True, False], repeat=len(keys)):
        checks = dict(zip(keys, combo))
        g = {"gates": checks, "all_pass": all(combo)}
        for delta in (None, 0.001, 0.05):
            v, _r = p82.classify_verdict_82(g, delta, True, [True, False], [True, False])
            assert v in ("V1_INCREMENTAL_INFORMATION_CONFIRMED", "V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT",
                        "V1_SIGNAL_PRESENT_BUT_UNSTABLE", "V1_TARGET_OR_PIPELINE_INVALID")


# --- J. no-trading-strategy / no-live-execution / safety --------------------
def test_no_trading_strategy_code():
    src = inspect.getsource(p82)
    for bad in ("place_order", "buy_signal", "sell_signal", "generate_signal", "stop_loss",
               "take_profit", "position_sizing", "execution_pipeline", "broker_adapter",
               "risk_gateway", "live_trading", "live_automation", "optimize_pnl", "sharpe"):
        assert bad not in src.lower()


def test_no_deep_learning_or_new_dependency():
    src = inspect.getsource(p82).lower()
    for bad in ("tensorflow", "torch", "keras", "lstm", "transformer", "xgboost", "lightgbm",
               "catboost", "optuna", "gpu", "cuda"):
        assert bad not in src


def test_frozen_holdout_never_accessed():
    src = inspect.getsource(p82)
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


def test_target_version_unchanged():
    import phase79_ml_target_integrity as p79
    assert p82.TARGET_VERSION == p79.V1_TARGET_SPEC.version == "V1-target-v1"


def test_module_imports_clean():
    import importlib
    importlib.reload(p82)
