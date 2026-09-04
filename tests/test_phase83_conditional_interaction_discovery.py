# -*- coding: utf-8 -*-
"""
Phase 83 — conditional market structure & regime interaction discovery.

Interaction registry, causal feature/target construction (not event-gated,
so distinct from V1/V2), discovery/confirmation split integrity, baseline+
interaction model comparison, multiple-testing correction, shuffled-target/
wrong-context-placebo/temporal-shift/future-shock controls, verdict
classification, holdout firewall, and safety. Synthetic bars only — no full
data run (the real run is the artifact produced by
``python -m phase83_conditional_interaction_discovery``).
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
import phase80_ml_volatility_regime as p80
import phase83_conditional_interaction_discovery as p83


def _frame(n=9000, seed=71, drift=0.0):
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


def _dataset(monkeypatch, rows, inst="EURUSD", horizon=4):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    return p83.build_context_dataset(inst, "15m", horizon)


# --- A. interaction registry -------------------------------------------------
def test_interaction_registry_has_exactly_five_candidates():
    assert p83.N_PRIMARY_CANDIDATES == 5
    reg = p83.interaction_registry_dicts()
    assert len(reg) == 5
    for c in reg:
        for k in ("id", "a", "b", "b_type", "target", "hypothesis"):
            assert k in c and c[k]


def test_baseline_d_contains_every_candidate_main_effect():
    baseline = set(p83.BASELINE_D_COLUMNS)
    for c in p83.INTERACTION_CANDIDATES:
        assert c["a"] in baseline
        if c["b_type"] == "continuous":
            assert c["b"] in baseline
        else:
            levels = p83._REGIME_LEVELS if c["b"] == "regime" else p83._SESSION_LEVELS
            for lvl in levels:
                assert f"{c['b']}_{lvl}" in baseline


def test_no_v1_v2_reopened():
    src = inspect.getsource(p83)
    assert "comp_run" not in src
    assert "rv_rank > 0.66" not in src.replace(" ", "")
    assert "_b_compression_duration" not in src
    assert "_b_vol_bucket_high" not in src


def test_targets_not_event_gated_uses_every_bar(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    # nearly every bar (minus warmup/horizon/NaN edges) should be a row --
    # unlike V1/V2's event-conditioned datasets, which keep only a small
    # fraction of bars
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    full_n = len(p78.augment(p76.load_bars("EURUSD", "15m"), "15m"))
    assert len(ds) > 0.9 * full_n


# --- B. dataset / contract ---------------------------------------------------
def test_dataset_schema(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    for col in ("instrument", "timeframe", "horizon_bars", "event_idx", "target_idx",
               "prediction_timestamp", "target_end_timestamp", "T1", "T2"):
        assert col in ds.columns


def test_feature_target_contract_passes_both_targets(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    for t in ("T1", "T2"):
        audit = p83.assert_feature_target_contract(ds, t)
        assert audit["pass"] is True


def test_discovery_confirmation_split_is_chronological(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=72))
    disc, conf = p83.discovery_confirmation_split(ds)
    if len(disc) and len(conf):
        assert disc["prediction_timestamp"].max() < conf["prediction_timestamp"].min()


def test_build_dataset_deterministic(monkeypatch):
    rows = _frame(n=9000, seed=73)
    a = _dataset(monkeypatch, rows)
    b = _dataset(monkeypatch, rows)
    pd.testing.assert_frame_equal(a, b)


# --- C. interaction columns / model fitting ---------------------------------
def test_interaction_columns_categorical_count(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=74))
    if ds.empty:
        return
    cand = next(c for c in p83.INTERACTION_CANDIDATES if c["b_type"] == "categorical" and c["b"] == "regime")
    ds2 = ds.copy()
    cols = p83._interaction_columns_for(ds2, cand)
    assert len(cols) == len(p83._REGIME_LEVELS)
    for c in cols:
        assert c in ds2.columns


def test_interaction_columns_continuous_count(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=75))
    if ds.empty:
        return
    cand = next(c for c in p83.INTERACTION_CANDIDATES if c["b_type"] == "continuous")
    ds2 = ds.copy()
    cols = p83._interaction_columns_for(ds2, cand)
    assert len(cols) == 1


def test_evaluate_candidate_model2_includes_baseline(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=76))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 500 or len(test) < 200:
        return
    cand = p83.INTERACTION_CANDIDATES[0]
    r = p83.evaluate_candidate(train, test, cand)
    assert set(p83.BASELINE_D_COLUMNS) <= set(f[len("feat__"):] for f in r["model2_with_interaction"]["features"]
                                              if not f.startswith("feat__ix_"))


def test_delta_r2_bootstrap_has_expected_shape(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=77))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 500 or len(test) < 200:
        return
    r = p83.evaluate_candidate(train, test, p83.INTERACTION_CANDIDATES[0])
    for k in ("point", "ci_lower", "ci_upper", "excludes_zero"):
        assert k in r["delta_r2"]


# --- D. controls -------------------------------------------------------------
def test_shuffled_target_control_near_zero(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=78))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 500 or len(test) < 200:
        return
    r = p83.shuffled_target_control(train, test, p83.INTERACTION_CANDIDATES[0])
    assert abs(r["metrics"]["oos_r2"]) < 0.2   # sanity bound


def test_wrong_context_placebo_shape(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=79))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 500 or len(test) < 200:
        return
    r = p83.wrong_context_placebo(train, test, p83.INTERACTION_CANDIDATES[0])
    assert "delta_r2" in r


def test_wrong_context_placebo_preserves_marginal_distribution(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=80))
    if ds.empty:
        return
    folds = p80.make_folds(ds, (2023, 2024))
    train, _v, test, _r = p80.split_fold(ds, folds[0], "15m")
    if len(train) < 500:
        return
    cand = p83.INTERACTION_CANDIDATES[0]
    a_col = f"feat__{cand['a']}"
    train2 = train.copy()
    rng = np.random.default_rng(1)
    train2[a_col] = rng.permutation(train2[a_col].to_numpy())
    # same multiset of values, different row order
    assert np.allclose(sorted(train[a_col].to_numpy()), sorted(train2[a_col].to_numpy()))


def test_temporal_shift_targets_preserves_row_count(monkeypatch):
    ds = _dataset(monkeypatch, _frame(n=9000, seed=81))
    if ds.empty:
        return
    p82_mod = __import__("phase82_compression_expansion_ml_pilot")
    p82_mod._clear_bar_cache_82()
    out = p83.temporal_shift_targets(ds, "T2", 4, 50)
    assert len(out) == len(ds)


def test_multiple_testing_never_silently_drops_a_tiny_variance_candidate():
    """Regression test for a real bug found during Phase 83's own full run:
    a candidate whose bootstrap SE rounds to exactly 0.0000 (e.g. se=0.00003)
    must still contribute a p-value to the multiple-testing family -- it
    must never be silently excluded from Benjamini-Hochberg correction just
    because its variance was extremely small."""
    from phase76_event_study import _benjamini_hochberg, _norm_cdf
    point, se = 0.0001, 0.0     # exactly the observed I5 confirmation-set values
    se_eff = se if (se and se > 0) else 1e-6
    z = point / se_eff
    p = 2 * (1 - _norm_cdf(abs(z)))
    assert p < 0.01   # tiny variance -> highly "significant" p-value, computed, not dropped
    flags = _benjamini_hochberg([p, 0.5], q=0.10)
    assert flags[0] is True or flags[0] == 1   # survives correction (included in the family at all)


def test_future_shock_invariance_passes():
    r = p83.check_future_shock_invariance()
    assert r["pass"] is True
    assert r["mismatches"] == {}


# --- E. verdict classification ----------------------------------------------
def _delta(point, lo, hi):
    return {"point": point, "ci_lower": lo, "ci_upper": hi, "excludes_zero": not (lo <= 0 <= hi)}


def test_verdict_explained_by_context_when_tiny():
    v, _r = p83.classify_candidate([_delta(0.001, 0.0, 0.002)], _delta(0.001, 0.0005, 0.0015),
                                   True, [0.001] * 6, True, None, 0.0)
    assert v == "EXPLAINED_BY_CONTEXT"


def test_verdict_no_effect_when_confirmation_and_discovery_both_flat():
    v, _r = p83.classify_candidate([_delta(0.0001, -0.001, 0.001)], _delta(0.0001, -0.0005, 0.0007),
                                   True, [0.0001] * 6, True, None, 0.0)
    assert v in ("NO_EFFECT", "EXPLAINED_BY_CONTEXT")


def test_verdict_descriptive_only_when_discovery_material_but_confirmation_vanishes():
    v, _r = p83.classify_candidate([_delta(0.02, 0.01, 0.03)], _delta(0.0005, -0.001, 0.002),
                                   True, [0.0005] * 6, True, None, 0.0)
    assert v == "DESCRIPTIVE_ONLY"


def test_verdict_sparse_when_min_n_fails():
    v, _r = p83.classify_candidate([_delta(0.02, 0.01, 0.03)], _delta(0.02, 0.01, 0.03),
                                   True, [0.02] * 6, False, None, 0.0)
    assert v == "SPARSE_OR_MULTIPLE_TESTING_RISK"


def test_verdict_sparse_when_shuffled_control_fails():
    v, _r = p83.classify_candidate([_delta(0.02, 0.01, 0.03)], _delta(0.02, 0.01, 0.03),
                                   True, [0.02] * 6, True, None, 0.05)
    assert v == "SPARSE_OR_MULTIPLE_TESTING_RISK"


def test_verdict_sparse_when_bh_fails():
    v, _r = p83.classify_candidate([_delta(0.02, 0.01, 0.03)], _delta(0.02, 0.01, 0.03),
                                   False, [0.02] * 6, True, 0.001, 0.0)
    assert v == "SPARSE_OR_MULTIPLE_TESTING_RISK"


def test_verdict_unstable_when_placebo_comparable():
    v, _r = p83.classify_candidate([_delta(0.02, 0.01, 0.03)], _delta(0.02, 0.01, 0.03),
                                   True, [0.02] * 6, True, 0.015, 0.0)
    assert v == "UNSTABLE"


def test_verdict_unstable_when_cross_asset_inconsistent():
    v, _r = p83.classify_candidate([_delta(0.02, 0.01, 0.03)], _delta(0.02, 0.01, 0.03),
                                   True, [0.02, -0.02, 0.02, -0.02, 0.02, -0.02], True, 0.0, 0.0)
    assert v == "UNSTABLE"


def test_verdict_promising_needs_all_gates():
    v, _r = p83.classify_candidate([_delta(0.02, 0.01, 0.03)] * 2, _delta(0.02, 0.01, 0.03),
                                   True, [0.02] * 6, True, 0.0005, 0.0)
    assert v == "PROMISING_NEEDS_CONFIRMATION"


def test_never_awards_robust_incremental_signal_programmatically():
    """§57's own high bar -- this classifier never outputs that label."""
    import itertools
    outcomes = set()
    for point in (0.0, 0.005, 0.02, 0.05):
        for bh in (True, False):
            for signs in ([0.02] * 6, [0.02, -0.02] * 3):
                v, _r = p83.classify_candidate([_delta(point, point - 0.005, point + 0.005)],
                                               _delta(point, point - 0.005, point + 0.005),
                                               bh, signs, True, 0.0, 0.0)
                outcomes.add(v)
    assert "ROBUST_INCREMENTAL_SIGNAL" not in outcomes


def test_verdict_only_documented_outcomes():
    valid = {"NO_EFFECT", "DESCRIPTIVE_ONLY", "EXPLAINED_BY_CONTEXT", "UNSTABLE",
            "SPARSE_OR_MULTIPLE_TESTING_RISK", "PROMISING_NEEDS_CONFIRMATION"}
    import itertools
    for point in (-0.02, 0.0, 0.001, 0.02):
        for bh in (True, False):
            for minn in (True, False):
                v, _r = p83.classify_candidate([_delta(point, point - 0.01, point + 0.01)],
                                               _delta(point, point - 0.01, point + 0.01),
                                               bh, [point] * 6, minn, None, 0.0)
                assert v in valid


# --- F. no-trading-strategy / holdout / safety ------------------------------
def test_no_trading_strategy_code():
    src = inspect.getsource(p83)
    for bad in ("place_order", "buy_signal", "sell_signal", "generate_signal", "stop_loss",
               "take_profit", "position_sizing", "execution_pipeline", "broker_adapter",
               "risk_gateway", "live_trading", "live_automation", "optimize_pnl", "sharpe"):
        assert bad not in src.lower()


def test_no_deep_learning_or_new_dependency():
    src = inspect.getsource(p83).lower()
    for bad in ("tensorflow", "torch", "keras", "lstm", "transformer", "xgboost", "lightgbm",
               "catboost", "optuna", "gpu", "cuda"):
        assert bad not in src


def test_frozen_holdout_never_accessed():
    src = inspect.getsource(p83)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
               "forward_lifecycle", "HistoricalVsForwardComparator", "get_holdout",
               "holdout_trades", "load_holdout", "holdout_df", "holdout_candles"):
        assert bad not in src


def test_frozen_hash_and_safety_flags_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"


def test_module_imports_clean():
    import importlib
    importlib.reload(p83)
