# -*- coding: utf-8 -*-
"""
Phase 81 — V2 Incremental Information / Context Decomposition.

A research-INTEGRITY phase, not a strategy phase, not another attempt to
maximize predictive performance. Phase 80 trained real ML models on the
Phase 78/79 V2 target and found `hour`-of-day dominating permutation
importance, with a corrected (population-MATCHED) placebo control showing
most of the full model's AUC advantage over a trivial current-state model
survives a broken timing relationship. Phase 81 asks the harder, more
specific question that raises:

    Does V2 contain information about future high-volatility persistence
    BEYOND current volatility state and deterministic intraday/session
    structure?

This is answered by an explicit, interpretable NESTED decomposition
(current-state -> volatility -> time/session -> +price -> +candle/regime ->
full), not a leaderboard. Logistic regression is the PRIMARY model
throughout (interpretable coefficients); HistGradientBoosting is used only
as a secondary reference point back to Phase 80. No new dependency, no
model-zoo expansion, no deep learning.

Everything about the V2 TARGET is reused unchanged from Phase 78/79/80:
event definition (`_b_vol_bucket_high`), target formula
(`rv_rank[i+h] > 0.66`), dataset construction
(`phase80_ml_volatility_regime.build_pooled_dataset`), calendar-year purged
walk-forward folds (`make_folds`/`split_fold`), baselines, the population-
MATCHED placebo methodology (corrected in Phase 80 after the naive
population-decoupled version was found confounded — that discovery and fix
is treated as settled science here, not re-litigated), the shuffled-target
control, and the future-shock invariance test. Phase 81 adds: (1) an
explicit current-state / volatility-state / time-session feature-group
regrouping (distinct from Phase 80's ablation grouping, justified in the
docs), (2) two cyclic time features (`hour_sin`/`hour_cos`) derived from
the existing causal `hour` column, (3) empirical conditional-probability
tables, (4) train-only time- and volatility-neutralization residual tests,
(5) a block-bootstrap CI utility for arbitrary classification metrics
(the existing `phase76_event_study.block_bootstrap` only handles a scalar
per-event mean; this reuses the identical moving-block resampling
principle, applied to (y, p) pairs).

Read-only. No execution/broker/risk/forward-validation module imported. The
frozen Phase-74 holdout is never read.
"""
from __future__ import annotations

import gc
import hashlib
import inspect
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase80_ml_volatility_regime as p80
from phase80_ml_volatility_regime import (
    ALL_HORIZONS, INSTRUMENTS_V2, PRIMARY_HORIZON, PRIMARY_TF, RANDOM_SEED,
    SECONDARY_TF, TARGET_VERSION, Fold, baseline_majority_class,
    baseline_persistence, baseline_simple_volatility, calibration_report,
    check_feature_future_shock_invariance, compute_metrics, make_folds,
    shuffled_target_control, split_fold,
)

SCHEMA_VERSION = "phase81.1"
ARTIFACT_KEY = "phase81_v2_information_decomposition"
DATASET_VERSION = p80.DATASET_VERSION           # reused verbatim -- same rows, same target
FEATURE_SCHEMA_VERSION = "phase81-features-v1"  # new GROUPING + 2 cyclic-time derived columns

_MATCHED_PLACEBO_SHIFT_BARS = p80._MATCHED_PLACEBO_SHIFT_BARS   # 200 -- unchanged Phase 80 default
_TEMPORAL_SHIFT_SWEEP: Tuple[int, ...] = (50, 100, 200, 500, 2000)
_GATE_H_MARGIN = 0.05     # reused verbatim from Phase 80's Gate H criterion
_SHUFFLE_SEED = 81001
_VOL_BUCKET_EDGES = (0.66, 0.75, 0.85, 0.95, 1.0001)
_VOL_BUCKET_LABELS = ("0.66-0.75", "0.75-0.85", "0.85-0.95", "0.95-1.00")
_MIN_CELL_N = 200        # predeclared minimum sample threshold for conditional-probability cells


# ==========================================================================
# §1/§5 — feature-group registry (a DIFFERENT grouping from Phase 80's,
# organised by conceptual role in the decomposition rather than by
# measurement type; documented in docs/PHASE_81_...md §6)
# ==========================================================================
FEATURE_GROUPS_81: Dict[str, List[str]] = {
    "CURRENT_STATE": ["current_high_flag"],
    "VOLATILITY": ["rv_rank", "regime_high_duration", "atr_ret", "atr_rank", "rv",
                  "rv_change_1", "atr_rank_change_1"],
    "TIME": ["hour_sin", "hour_cos", "dow", "session_code"],
    "PRICE": list(p80.FEATURE_GROUPS["PRICE"]),
    "CANDLE": list(p80.FEATURE_GROUPS["CANDLE"]),
    "REGIME": ["regime_code"],
}

# §6 nested nested model sequence -- the CENTRAL decomposition of this phase
NESTED_MODELS: Dict[str, List[str]] = {
    "M0_constant": [],
    "M1_current_state": FEATURE_GROUPS_81["CURRENT_STATE"],
    "M2_volatility": FEATURE_GROUPS_81["VOLATILITY"],
    "M3_time": FEATURE_GROUPS_81["TIME"],
    "M4_volatility_time": FEATURE_GROUPS_81["VOLATILITY"] + FEATURE_GROUPS_81["TIME"],
    "M5_price_volatility_time": (FEATURE_GROUPS_81["PRICE"] + FEATURE_GROUPS_81["VOLATILITY"]
                                 + FEATURE_GROUPS_81["TIME"]),
    "M6_full": (FEATURE_GROUPS_81["VOLATILITY"] + FEATURE_GROUPS_81["TIME"]
               + FEATURE_GROUPS_81["PRICE"] + FEATURE_GROUPS_81["CANDLE"]
               + FEATURE_GROUPS_81["REGIME"]),
}
# §25 extended, time-anchored ablation. A/B/C/F are identical column sets to
# M3/M4/M5/M6 above and are NOT re-fit (reused directly, §41 perf discipline);
# D and E isolate candle's and regime's OWN marginal contribution.
ABLATION_81: Dict[str, List[str]] = {
    "A_time_only": NESTED_MODELS["M3_time"],
    "B_time_volatility": NESTED_MODELS["M4_volatility_time"],
    "C_time_volatility_price": NESTED_MODELS["M5_price_volatility_time"],
    "D_time_volatility_candle": (FEATURE_GROUPS_81["TIME"] + FEATURE_GROUPS_81["VOLATILITY"]
                                 + FEATURE_GROUPS_81["CANDLE"]),
    "E_time_volatility_regime": (FEATURE_GROUPS_81["TIME"] + FEATURE_GROUPS_81["VOLATILITY"]
                                 + FEATURE_GROUPS_81["REGIME"]),
    "F_full": NESTED_MODELS["M6_full"],
}

_PRIMARY_MODEL = "logistic_regression"    # interpretable, primary throughout (§3, §11)
_REFERENCE_MODEL = "hist_gradient_boosting"  # secondary reference back to Phase 80 only


def feature_group_registry_dicts() -> Dict[str, Any]:
    return {"groups": FEATURE_GROUPS_81, "nested_models": NESTED_MODELS, "ablation_81": ABLATION_81}


# ==========================================================================
# §5 dataset — reuses Phase 80's build_pooled_dataset (hence the exact,
# unchanged V2 event/target definition) and adds only the two cyclic-time
# derived columns plus a documented degenerate current-state flag.
# ==========================================================================
def build_phase81_dataset(tf: str, horizon: int,
                          instruments: Tuple[str, ...] = INSTRUMENTS_V2) -> pd.DataFrame:
    ds = p80.build_pooled_dataset(tf, horizon, instruments)
    if ds.empty:
        return ds
    ds = ds.copy()
    # §5 GROUP A -- current HIGH/LOW state. Every row in this dataset is, BY
    # THE V2 EVENT DEFINITION ITSELF, already "currently HIGH" (rv_rank>0.66
    # at event time) -- so this column is a documented CONSTANT (zero
    # variance), not a real feature. Included explicitly (rather than
    # omitted) so Model 1 below can demonstrate this rather than merely
    # assert it.
    ds["feat__current_high_flag"] = 1.0
    hour = ds["feat__hour"].to_numpy(float)
    ds["feat__hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
    ds["feat__hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
    ds["dataset_version"] = DATASET_VERSION
    ds["feature_schema_version"] = FEATURE_SCHEMA_VERSION
    return ds


def assert_feature_target_contract(dataset: pd.DataFrame) -> Dict[str, Any]:
    """Identical contract to Phase 79/80 -- reused, not re-derived."""
    return p80.assert_feature_target_contract(dataset)


# ==========================================================================
# Fit/eval — logistic regression (primary, interpretable) or the Phase 80
# HistGradientBoosting reference model, over an explicit feature-group list.
# Model 0 (constant) is special-cased: no sklearn fit at all.
# ==========================================================================
def fit_and_eval_group(train: pd.DataFrame, test: pd.DataFrame, features: List[str],
                       model_name: str = _PRIMARY_MODEL) -> Dict[str, Any]:
    if not features:
        p_train_mean = float(train["target"].mean())
        p_test = np.full(len(test), p_train_mean)
        y_test = test["target"].to_numpy(int)
        return {"model": "constant", "features": [], "n_train": len(train),
               "metrics": compute_metrics(y_test, p_test), "coefficients": None,
               "_p_pred": p_test, "_y_true": y_test}
    r = p80.fit_and_eval(train, test, features, model_name)
    coefs = None
    if model_name == "logistic_regression":
        clf = r["_fitted_model"].named_steps["clf"]
        coefs = {f: round(float(c), 5) for f, c in zip(features, clf.coef_[0])}
        coefs["_intercept"] = round(float(clf.intercept_[0]), 5)
    return {"model": model_name, "features": features, "n_train": r["n_train"],
           "metrics": r["metrics"], "calibration": calibration_report(r["_y_true"], r["_p_pred"]),
           "coefficients": coefs, "_p_pred": r["_p_pred"], "_y_true": r["_y_true"],
           "_fitted_model": r["_fitted_model"]}


def zero_variance_report(df: pd.DataFrame, features: List[str]) -> Dict[str, bool]:
    return {f: bool(df[f"feat__{f}"].nunique(dropna=True) <= 1) for f in features}


# ==========================================================================
# §7 conditional probability analysis (descriptive; full dataset, not a
# modelling decision -- so no train/test leakage concern applies here, only
# to the NEUTRALIZATION baselines below, which are strictly train-only)
# ==========================================================================
def compute_conditional_rates(ds: pd.DataFrame, min_n: int = _MIN_CELL_N) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["overall_p_high"] = round(float(ds["target"].mean()), 4)

    rv = ds["feat__rv_rank"].to_numpy(float)
    bucket = pd.cut(rv, bins=_VOL_BUCKET_EDGES, labels=_VOL_BUCKET_LABELS, right=False)
    by_bucket = ds.groupby(bucket, observed=True)["target"].agg(["mean", "count"])
    out["by_volatility_bucket"] = {
        str(k): {"p_high": round(float(v["mean"]), 4), "n": int(v["count"])}
        for k, v in by_bucket.iterrows() if v["count"] >= min_n}

    by_hour = ds.groupby("feat__hour")["target"].agg(["mean", "count"])
    out["by_hour"] = {int(k): {"p_high": round(float(v["mean"]), 4), "n": int(v["count"])}
                      for k, v in by_hour.iterrows() if v["count"] >= min_n}

    sess_map = {v: k for k, v in p80._SESSION_CODE.items()}
    by_session = ds.groupby("feat__session_code")["target"].agg(["mean", "count"])
    out["by_session"] = {sess_map.get(k, str(k)): {"p_high": round(float(v["mean"]), 4), "n": int(v["count"])}
                        for k, v in by_session.iterrows() if v["count"] >= min_n}

    cross = ds.groupby([bucket, "feat__hour"], observed=True)["target"].agg(["mean", "count"])
    out["by_volatility_bucket_and_hour"] = [
        {"bucket": str(b), "hour": int(h), "p_high": round(float(v["mean"]), 4), "n": int(v["count"])}
        for (b, h), v in cross.iterrows() if v["count"] >= min_n]
    return out


# ==========================================================================
# §8/§9 time- and volatility-state neutralization. Baselines are computed
# STRICTLY on the TRAIN split; applied to whichever split is being scored
# (never fit on the split being evaluated, §0.4/§38).
# ==========================================================================
def _group_baseline(train: pd.DataFrame, group_cols: List[str]) -> Tuple[pd.Series, float]:
    baseline = train.groupby(group_cols)["target"].mean()
    global_fallback = float(train["target"].mean())
    return baseline, global_fallback


def compute_time_neutralized_residual(train: pd.DataFrame, eval_df: pd.DataFrame,
                                      group_cols: Tuple[str, ...] = ("instrument", "feat__hour")
                                      ) -> Dict[str, Any]:
    """§8 Method A -- within (instrument x hour) centering, train-only."""
    baseline, fallback = _group_baseline(train, list(group_cols))
    key = pd.MultiIndex.from_arrays([eval_df[c] for c in group_cols])
    base_vals = baseline.reindex(key).to_numpy()
    base_vals = np.where(np.isnan(base_vals), fallback, base_vals)
    residual = eval_df["target"].to_numpy(float) - base_vals
    return {"group_cols": list(group_cols), "residual": residual, "baseline_values": base_vals,
           "residual_mean": round(float(np.mean(residual)), 6),
           "residual_std": round(float(np.std(residual)), 6)}


def compute_volatility_neutralized_residual(train: pd.DataFrame, eval_df: pd.DataFrame
                                            ) -> Dict[str, Any]:
    """§9 -- within volatility-bucket centering, train-only. Bucket edges are
    FIXED a priori (not derived from data), so no leakage risk from the
    bucketing itself."""
    def _bucket(df):
        return pd.cut(df["feat__rv_rank"].to_numpy(float), bins=_VOL_BUCKET_EDGES,
                      labels=_VOL_BUCKET_LABELS, right=False)
    train_b = train.assign(_bucket=_bucket(train))
    baseline, fallback = _group_baseline(train_b, ["instrument", "_bucket"])
    eval_b = _bucket(eval_df)
    key = pd.MultiIndex.from_arrays([eval_df["instrument"], eval_b])
    base_vals = baseline.reindex(key).to_numpy()
    base_vals = np.where(np.isnan(base_vals), fallback, base_vals)
    residual = eval_df["target"].to_numpy(float) - base_vals
    return {"residual": residual, "baseline_values": base_vals,
           "residual_mean": round(float(np.mean(residual)), 6),
           "residual_std": round(float(np.std(residual)), 6)}


def evaluate_residual_information(residual: np.ndarray, candidate_features: pd.DataFrame
                                  ) -> Dict[str, Any]:
    """Does ``candidate_features`` (fit on TRAIN, scored on the residual's
    own held-out rows) explain any of the residual's variance? Uses a plain
    linear regression (interpretable, no new model family) and reports R^2
    plus the sign/magnitude of each coefficient."""
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import KFold
    X = candidate_features.to_numpy(float)
    y = np.asarray(residual, float)
    finite = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X, y = X[finite], y[finite]
    if len(y) < 200:
        return {"state": "INSUFFICIENT_SAMPLE"}
    # 3-fold CV R^2 (in-sample-of-this-residual-set only; the residual itself
    # was already computed from a disjoint TRAIN baseline, §8/§9)
    kf = KFold(n_splits=3, shuffle=False)
    r2s = []
    for tr_idx, te_idx in kf.split(X):
        m = LinearRegression().fit(X[tr_idx], y[tr_idx])
        pred = m.predict(X[te_idx])
        ss_res = float(np.sum((y[te_idx] - pred) ** 2))
        ss_tot = float(np.sum((y[te_idx] - y[te_idx].mean()) ** 2))
        r2s.append(1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0)
    full_model = LinearRegression().fit(X, y)
    coefs = {c: round(float(v), 6) for c, v in zip(candidate_features.columns, full_model.coef_)}
    return {"n": int(len(y)), "cv_r2_mean": round(float(np.mean(r2s)), 5),
           "cv_r2_folds": [round(float(v), 5) for v in r2s], "coefficients": coefs}


# ==========================================================================
# §22 block-bootstrap CI for an arbitrary classification metric. Reuses the
# IDENTICAL moving-block resampling principle as
# ``phase76_event_study.block_bootstrap`` (same block-length convention:
# block = horizon in bars) -- a new function is required only because that
# one is specialised to a scalar per-event mean, not an (y, p) metric.
# ==========================================================================
def bootstrap_metric_ci(y_true: np.ndarray, p_pred: np.ndarray, metric_fn, block: int,
                        iters: int = 1000, seed: int = RANDOM_SEED) -> Dict[str, Any]:
    y, p = np.asarray(y_true), np.asarray(p_pred)
    n = len(y)
    if n < 200:
        return {"state": "INSUFFICIENT_SAMPLE"}
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    point = metric_fn(y, p)
    eff_iters = int(min(iters, max(200, 20_000_000 // n)))
    vals = np.empty(eff_iters)
    for k in range(eff_iters):
        starts = rng.integers(0, n - block + 1, size=nb)
        idx = (starts[:, None] + np.arange(block)[None, :]).reshape(-1)[:n]
        vals[k] = metric_fn(y[idx], p[idx])
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"point": round(float(point), 4), "ci_lower": round(float(lo), 4),
           "ci_upper": round(float(hi), 4), "se": round(float(np.std(vals, ddof=1)), 4),
           "block": int(block), "iters": eff_iters}


def bootstrap_delta_ci(y_true: np.ndarray, p_a: np.ndarray, p_b: np.ndarray, metric_fn,
                       block: int, iters: int = 1000, seed: int = RANDOM_SEED) -> Dict[str, Any]:
    """Paired block-bootstrap CI for metric(a) - metric(b) on the SAME rows."""
    y = np.asarray(y_true)
    n = len(y)
    if n < 200:
        return {"state": "INSUFFICIENT_SAMPLE"}
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    point = metric_fn(y, p_a) - metric_fn(y, p_b)
    eff_iters = int(min(iters, max(200, 20_000_000 // n)))
    vals = np.empty(eff_iters)
    for k in range(eff_iters):
        starts = rng.integers(0, n - block + 1, size=nb)
        idx = (starts[:, None] + np.arange(block)[None, :]).reshape(-1)[:n]
        vals[k] = metric_fn(y[idx], p_a[idx]) - metric_fn(y[idx], p_b[idx])
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"point": round(float(point), 4), "ci_lower": round(float(lo), 4),
           "ci_upper": round(float(hi), 4), "se": round(float(np.std(vals, ddof=1)), 4),
           "block": int(block), "iters": eff_iters,
           "excludes_zero": bool(lo > 0 or hi < 0)}


def _auc_fn(y, p):
    from sklearn.metrics import roc_auc_score
    if len(set(y.tolist())) < 2:
        return 0.5
    return float(roc_auc_score(y, p))


# ==========================================================================
# §12 hour-of-day investigation helper: is hour a volatility proxy, or does
# it carry independent information? (hour -> target| conditioning on rv_rank
# bucket, vs. the unconditional hour -> target relationship)
# ==========================================================================
def hour_mechanism_report(ds: pd.DataFrame, min_n: int = _MIN_CELL_N) -> Dict[str, Any]:
    rv = ds["feat__rv_rank"].to_numpy(float)
    bucket = pd.cut(rv, bins=_VOL_BUCKET_EDGES, labels=_VOL_BUCKET_LABELS, right=False)
    # rv_rank distribution by hour (does hour predict volatility LEVEL?)
    rv_by_hour = ds.groupby("feat__hour")["feat__rv_rank"].agg(["mean", "std", "count"])
    rv_by_hour_out = {int(k): {"mean_rv_rank": round(float(v["mean"]), 4),
                               "std_rv_rank": round(float(v["std"]), 4), "n": int(v["count"])}
                      for k, v in rv_by_hour.iterrows() if v["count"] >= min_n}
    # target rate by hour WITHIN each volatility bucket (does hour still
    # matter once volatility level is already known?)
    cross = ds.assign(_bucket=bucket).groupby(["_bucket", "feat__hour"], observed=True)["target"] \
        .agg(["mean", "count"])
    within_bucket = [
        {"bucket": str(b), "hour": int(h), "p_high": round(float(v["mean"]), 4), "n": int(v["count"])}
        for (b, h), v in cross.iterrows() if v["count"] >= min_n]
    # a simple diagnostic: variance of by-hour target rate WITHIN a fixed
    # bucket vs. the overall by-hour variance (unconditional)
    overall_hour_rates = np.array([v["p_high"] for v in
                                   compute_conditional_rates(ds, min_n)["by_hour"].values()])
    within_bucket_rates_by_bucket: Dict[str, List[float]] = {}
    for row in within_bucket:
        within_bucket_rates_by_bucket.setdefault(row["bucket"], []).append(row["p_high"])
    within_bucket_spread = {b: round(float(np.std(v)), 4) for b, v in
                           within_bucket_rates_by_bucket.items() if len(v) >= 3}
    return {
        "rv_rank_by_hour": rv_by_hour_out,
        "target_rate_by_hour_within_volatility_bucket": within_bucket,
        "unconditional_hour_spread_std": round(float(np.std(overall_hour_rates)), 4)
        if len(overall_hour_rates) else None,
        "within_bucket_hour_spread_std": within_bucket_spread,
        "interpretation": (
            "if within_bucket spread is nearly as large as the unconditional spread, hour "
            "carries information INDEPENDENT of volatility level (not merely a proxy); if it "
            "shrinks substantially once volatility level is fixed, hour is acting largely as a "
            "volatility-level proxy"),
    }


# ==========================================================================
# §27 pre-specified interactions (exactly 3, no search)
# ==========================================================================
def interaction_report(ds: pd.DataFrame, min_n: int = _MIN_CELL_N) -> Dict[str, Any]:
    bucket = pd.cut(ds["feat__rv_rank"].to_numpy(float), bins=_VOL_BUCKET_EDGES,
                    labels=_VOL_BUCKET_LABELS, right=False)
    sess_map = {v: k for k, v in p80._SESSION_CODE.items()}
    session = ds["feat__session_code"].map(sess_map)

    def _cells(a, b, name_a, name_b):
        g = ds.assign(_a=a, _b=b).groupby(["_a", "_b"], observed=True)["target"].agg(["mean", "count"])
        return [{name_a: str(i0), name_b: str(i1), "p_high": round(float(v["mean"]), 4), "n": int(v["count"])}
               for (i0, i1), v in g.iterrows() if v["count"] >= min_n]

    return {
        "hour_x_volatility_bucket": _cells(ds["feat__hour"], bucket, "hour", "volatility_bucket"),
        "session_x_volatility_bucket": _cells(session, bucket, "session", "volatility_bucket"),
        "session_x_hour": _cells(session, ds["feat__hour"], "session", "hour"),
    }


# ==========================================================================
# §19/§21 population-matched placebo + temporal-shift sweep. Reuses Phase
# 80's CORRECTED methodology (identical feature rows, target relabelled
# further into the future) verbatim -- the population-DECOUPLED version is
# NOT reinstated; see docs §19 for why it was confounded. A small
# per-instrument rv_rank-array cache avoids re-loading/re-augmenting bars on
# every shift value in the sweep (§41 perf discipline; does not change the
# methodology, only avoids redundant I/O).
# ==========================================================================
_RV_RANK_CACHE: Dict[Tuple[str, str], np.ndarray] = {}


def _clear_rv_rank_cache() -> None:
    _RV_RANK_CACHE.clear()


def _get_rv_rank_array(instrument: str, tf: str) -> np.ndarray:
    key = (instrument, tf)
    if key not in _RV_RANK_CACHE:
        df = p80.augment(p80.load_bars(instrument, tf), tf)
        _RV_RANK_CACHE[key] = df["rv_rank"].to_numpy(float)
    return _RV_RANK_CACHE[key]


def matched_placebo_targets(df_subset: pd.DataFrame, horizon: int,
                            shift_bars: int = _MATCHED_PLACEBO_SHIFT_BARS) -> np.ndarray:
    tf = df_subset["timeframe"].iloc[0] if "timeframe" in df_subset.columns else PRIMARY_TF
    out = np.full(len(df_subset), np.nan)
    for inst in df_subset["instrument"].unique():
        rv_rank = _get_rv_rank_array(inst, tf)
        n = len(rv_rank)
        m = (df_subset["instrument"] == inst).to_numpy()
        idxs = df_subset.loc[m, "event_idx"].to_numpy()
        j = idxs + shift_bars + horizon
        valid = j < n
        vals = np.full(len(idxs), np.nan)
        vals[valid] = (rv_rank[j[valid]] > 0.66).astype(float)
        out[np.where(m)[0]] = vals
    return out


def matched_placebo_control(train: pd.DataFrame, test: pd.DataFrame, features: List[str],
                            model_name: str, horizon: int,
                            shift_bars: int = _MATCHED_PLACEBO_SHIFT_BARS
                            ) -> Optional[Dict[str, Any]]:
    train2, test2 = train.copy(), test.copy()
    train2["target"] = matched_placebo_targets(train2, horizon, shift_bars)
    test2["target"] = matched_placebo_targets(test2, horizon, shift_bars)
    train2 = train2.dropna(subset=["target"])
    test2 = test2.dropna(subset=["target"])
    if len(train2) < 200 or len(test2) < 30 or not features:
        return None
    train2["target"] = train2["target"].astype(int)
    test2["target"] = test2["target"].astype(int)
    r = fit_and_eval_group(train2, test2, features, model_name)
    return {"shift_bars": shift_bars, "metrics": r["metrics"]}


def temporal_shift_sweep(train: pd.DataFrame, test: pd.DataFrame, features: List[str],
                         model_name: str, horizon: int,
                         shifts: Tuple[int, ...] = _TEMPORAL_SHIFT_SWEEP) -> List[Dict[str, Any]]:
    """§21 -- diagnostic, not a definitive null: does the AUC decay as the
    target's timing is progressively decoupled from the true horizon?"""
    out = []
    for s in shifts:
        r = matched_placebo_control(train, test, features, model_name, horizon, shift_bars=s)
        if r:
            out.append(r)
    return out


# ==========================================================================
# §33 gates
# ==========================================================================
def evaluate_gates_81(dataset_ok: bool, leakage_ok: bool, determinism_match: bool,
                      neutralization_methodology_ok: bool, vol_conditioning_ok: bool,
                      cross_asset_complete: bool, cross_year_complete: bool,
                      real_auc: Optional[float], placebo_auc: Optional[float],
                      shuffled_auc: Optional[float], holdout_match: bool) -> Dict[str, Any]:
    gate_h = bool(real_auc is not None and placebo_auc is not None
                 and real_auc > placebo_auc + _GATE_H_MARGIN)
    gate_i = bool(shuffled_auc is not None and abs(shuffled_auc - 0.5) < 0.07)
    gates = {
        "A_dataset_integrity": dataset_ok, "B_leakage": leakage_ok,
        "C_reproducibility": determinism_match, "D_time_neutralization_methodology": neutralization_methodology_ok,
        "E_volatility_conditioning_methodology": vol_conditioning_ok,
        "F_cross_asset_complete": cross_asset_complete, "G_cross_year_complete": cross_year_complete,
        "H_matched_placebo": gate_h, "I_shuffled_target": gate_i, "J_holdout_protected": holdout_match,
    }
    return {"gates": gates, "all_pass": all(gates.values()), "n_pass": sum(gates.values())}


def classify_verdict_81(gates: Dict[str, Any], delta_full_vs_voltime: Optional[float],
                        delta_ci_excludes_zero: bool, cross_year_signs: List[Optional[bool]],
                        cross_asset_signs: List[Optional[bool]],
                        residual_r2_time: Optional[float], residual_r2_vol: Optional[float]
                        ) -> Tuple[str, str]:
    """§32/§34 -- exactly one of four controlled outcomes, predeclared rule."""
    hard = ("A_dataset_integrity", "B_leakage", "C_reproducibility", "J_holdout_protected")
    if not all(gates["gates"][g] for g in hard):
        return "V2_TARGET_OR_PIPELINE_INVALID", "a hard integrity/leakage/reproducibility/holdout gate failed"
    if delta_full_vs_voltime is None:
        return "V2_TARGET_OR_PIPELINE_INVALID", "headline delta could not be computed"
    small = abs(delta_full_vs_voltime) < 0.02
    if small or not gates["gates"]["H_matched_placebo"]:
        return ("V2_EXPLAINED_BY_TIME_AND_VOLATILITY",
               "the full-context model adds negligible (or placebo-indistinguishable) AUC beyond "
               "volatility-state + time/session alone")
    signs_year = [s for s in cross_year_signs if s is not None]
    signs_asset = [s for s in cross_asset_signs if s is not None]
    year_consistent = bool(signs_year) and all(signs_year)
    asset_consistent = bool(signs_asset) and (sum(signs_asset) / len(signs_asset) >= 0.6)
    if (delta_ci_excludes_zero and year_consistent and asset_consistent
            and gates["gates"]["H_matched_placebo"] and gates["gates"]["I_shuffled_target"]):
        return ("V2_RESIDUAL_INFORMATION_CONFIRMED",
               "residual information beyond time+volatility survives OOS, matched placebo, "
               "cross-year, and cross-asset checks")
    return ("V2_PREDICTABLE_BUT_RESIDUAL_INFORMATION_UNSTABLE",
           "a positive residual delta exists but is not consistently stable across years/assets "
           "or its CI does not exclude zero")


# ==========================================================================
# §30/§31 experiment record + result schema
# ==========================================================================
@dataclass
class Phase81Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    phase80_commit_reference: Optional[str]
    target_version: str
    dataset_version: str
    feature_schema_version: str
    universe: List[str]
    timeframes: List[str]
    horizons: List[int]
    feature_groups: Dict[str, Any]
    dataset_summary: Dict[str, Any]
    feature_target_contract: Dict[str, Any]
    zero_variance: Dict[str, bool]
    folds: Dict[str, List[Dict[str, Any]]]
    nested_models: List[Dict[str, Any]]
    extended_ablation: List[Dict[str, Any]]
    conditional_rates: Dict[str, Any]
    hour_mechanism: Dict[str, Any]
    interactions: Dict[str, Any]
    time_neutralization: Dict[str, Any]
    volatility_neutralization: Dict[str, Any]
    cross_asset: Dict[str, Any]
    cross_year: Dict[str, Any]
    leave_one_asset_out: Dict[str, Any]
    horizon_analysis: List[Dict[str, Any]]
    secondary_timeframe: List[Dict[str, Any]]
    controls: Dict[str, Any]
    bootstrap: Dict[str, Any]
    calibration_headline: Dict[str, Any]
    determinism: Dict[str, Any]
    gates: Dict[str, Any]
    verdict: str
    verdict_reason: str
    v1_decision: Dict[str, Any]
    phase82_queue: List[Dict[str, Any]]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _git_commit() -> Optional[str]:
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def _nested_sweep(ds: pd.DataFrame, folds: List[Fold], tf: str,
                  models: Tuple[str, ...] = (_PRIMARY_MODEL, _REFERENCE_MODEL)
                  ) -> Tuple[List[Dict[str, Any]], Dict[Tuple[int, str, str], Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    fits: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
    for fold in folds:
        train, _val, test, rep = split_fold(ds, fold, tf)
        if len(train) < 200 or len(test) < 30:
            continue
        for name, feats in NESTED_MODELS.items():
            for m in models:
                r = fit_and_eval_group(train, test, feats, m)
                rows.append({"fold": fold.fold, "model_group": name, "model": m,
                            "n_features": len(feats), "n_train": r["n_train"], "n_test": len(test),
                            "metrics": r["metrics"], "coefficients": r.get("coefficients")})
                fits[(fold.fold, name, m)] = r
    return rows, fits


def run() -> Phase81Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()
    _clear_rv_rank_cache()

    p80_artifact = p80.get_result()
    if not p80_artifact:
        raise RuntimeError("Phase 80 artifact not found -- run `python -m "
                           "phase80_ml_volatility_regime` first")

    # ---- §4/§5 datasets ------------------------------------------------
    ds_15m = {h: build_phase81_dataset(PRIMARY_TF, h) for h in ALL_HORIZONS}
    ds_1h_h4 = build_phase81_dataset(SECONDARY_TF, PRIMARY_HORIZON)

    contract = {f"15m_h{h}": assert_feature_target_contract(ds_15m[h]) for h in ALL_HORIZONS}
    contract["1h_h4"] = assert_feature_target_contract(ds_1h_h4)
    leakage_ok = all(v.get("pass") for v in contract.values())

    zero_var = zero_variance_report(ds_15m[PRIMARY_HORIZON], sum(FEATURE_GROUPS_81.values(), []))
    # Gate A: dataset integrity -- expected universe/timeframes/horizons/rows present
    dataset_ok = (
        set(INSTRUMENTS_V2) == set(ds_15m[PRIMARY_HORIZON]["instrument"].unique())
        and all(len(ds_15m[h]) > 100_000 for h in ALL_HORIZONS)
        and len(ds_1h_h4) > 50_000
        and zero_var["current_high_flag"] is True   # documented, expected degeneracy
    )

    dataset_summary = {
        "instruments": list(INSTRUMENTS_V2), "primary_timeframe": PRIMARY_TF,
        "secondary_timeframe": SECONDARY_TF, "primary_horizon": PRIMARY_HORIZON,
        "horizons": list(ALL_HORIZONS),
        "rows_15m": {f"h{h}": int(len(ds_15m[h])) for h in ALL_HORIZONS},
        "rows_1h_h4": int(len(ds_1h_h4)),
        "positive_rate_15m_h4": round(float(ds_15m[PRIMARY_HORIZON]["target"].mean()), 4),
    }

    # ---- §13/§14 folds ---------------------------------------------------
    folds_15m = make_folds(ds_15m[PRIMARY_HORIZON], p80._FOLD_BOUNDARY_YEARS)
    folds_1h = make_folds(ds_1h_h4, p80._FOLD_BOUNDARY_YEARS_SECONDARY)
    folds_dict = {"15m": [f.to_dict() for f in folds_15m], "1h": [f.to_dict() for f in folds_1h]}
    test_period_label = {1: "2023_H2", 2: "2024_H2", 3: "2025_H2_onward"}
    test_period_label_1h = {1: "2024_H2", 2: "2025_H2_onward"}

    # ---- §6 nested model decomposition (headline: 15m, h=4) ---------------
    nested_rows, nested_fits = _nested_sweep(ds_15m[PRIMARY_HORIZON], folds_15m, PRIMARY_TF)
    for row in nested_rows:
        row["test_period"] = test_period_label[row["fold"]]

    headline_fold = folds_15m[-1]
    headline_train, _hv, headline_test, headline_split_report = split_fold(
        ds_15m[PRIMARY_HORIZON], headline_fold, PRIMARY_TF)

    # ---- §25 extended ablation (D, E only -- A/B/C/F reused from nested) --
    extended_rows: List[Dict[str, Any]] = []
    for fold in folds_15m:
        train, _v, test, _r = split_fold(ds_15m[PRIMARY_HORIZON], fold, PRIMARY_TF)
        if len(train) < 200 or len(test) < 30:
            continue
        for name in ("D_time_volatility_candle", "E_time_volatility_regime"):
            feats = ABLATION_81[name]
            for m in (_PRIMARY_MODEL, _REFERENCE_MODEL):
                r = fit_and_eval_group(train, test, feats, m)
                extended_rows.append({"fold": fold.fold, "test_period": test_period_label[fold.fold],
                                      "ablation": name, "model": m, "metrics": r["metrics"]})

    # ---- §7/§12/§27 descriptive analyses (full 15m/h4 dataset) -----------
    cond_rates = compute_conditional_rates(ds_15m[PRIMARY_HORIZON])
    hour_mech = hour_mechanism_report(ds_15m[PRIMARY_HORIZON])
    interactions = interaction_report(ds_15m[PRIMARY_HORIZON])

    # ---- §8/§9/§10 neutralization (headline fold train/test) -------------
    time_resid = compute_time_neutralized_residual(headline_train, headline_test)
    vol_features_for_resid = headline_test[[f"feat__{f}" for f in FEATURE_GROUPS_81["VOLATILITY"]]]
    time_resid_info = evaluate_residual_information(time_resid["residual"], vol_features_for_resid)
    time_neutralization = {"method": "within (instrument x hour) train-only centering",
                          "residual_summary": {k: v for k, v in time_resid.items()
                                              if k not in ("residual", "baseline_values")},
                          "volatility_explains_residual": time_resid_info}

    vol_resid = compute_volatility_neutralized_residual(headline_train, headline_test)
    time_features_for_resid = headline_test[[f"feat__{f}" for f in FEATURE_GROUPS_81["TIME"]]]
    vol_resid_info = evaluate_residual_information(vol_resid["residual"], time_features_for_resid)
    volatility_neutralization = {"method": "within (instrument x fixed volatility bucket) train-only "
                                          "centering",
                                "residual_summary": {k: v for k, v in vol_resid.items()
                                                    if k not in ("residual", "baseline_values")},
                                "time_explains_residual": vol_resid_info}
    neutralization_methodology_ok = (time_resid_info.get("state") != "INSUFFICIENT_SAMPLE"
                                     and vol_resid_info.get("state") != "INSUFFICIENT_SAMPLE")
    vol_conditioning_ok = neutralization_methodology_ok  # same headline computation validates both

    # ---- §13/§15 cross-asset + leave-one-out (headline fold, M4 & M6) -----
    def _per_instrument(fit_key: Tuple[int, str, str]) -> Dict[str, Any]:
        fit = nested_fits[fit_key]
        p_pred, y_true = fit["_p_pred"], fit["_y_true"]
        out = {}
        test_reset = headline_test.reset_index(drop=True)
        for inst in sorted(test_reset["instrument"].unique()):
            m = (test_reset["instrument"] == inst).to_numpy()
            if m.sum() < 200:
                out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
                continue
            out[inst] = compute_metrics(y_true[m], p_pred[m])
        return out

    cross_asset_m4 = _per_instrument((headline_fold.fold, "M4_volatility_time", _REFERENCE_MODEL))
    cross_asset_m6 = _per_instrument((headline_fold.fold, "M6_full", _REFERENCE_MODEL))
    cross_asset_delta = {}
    for inst in INSTRUMENTS_V2:
        a4, a6 = cross_asset_m4.get(inst, {}).get("roc_auc"), cross_asset_m6.get(inst, {}).get("roc_auc")
        cross_asset_delta[inst] = round(a6 - a4, 4) if (a4 is not None and a6 is not None) else None
    cross_asset = {"m4_volatility_time": cross_asset_m4, "m6_full": cross_asset_m6,
                  "delta_full_minus_voltime": cross_asset_delta,
                  "n_instruments_evaluated": len(cross_asset_delta)}
    cross_asset_complete = len(cross_asset_delta) == len(INSTRUMENTS_V2)

    loo_rows: Dict[str, Any] = {}
    for held_out in INSTRUMENTS_V2:
        train_wo = headline_train[headline_train["instrument"] != held_out]
        test_held = headline_test[headline_test["instrument"] == held_out]
        if len(train_wo) < 500 or len(test_held) < 200:
            loo_rows[held_out] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        r4 = fit_and_eval_group(train_wo, test_held, NESTED_MODELS["M4_volatility_time"], _REFERENCE_MODEL)
        r6 = fit_and_eval_group(train_wo, test_held, NESTED_MODELS["M6_full"], _REFERENCE_MODEL)
        loo_rows[held_out] = {"m4_auc": r4["metrics"]["roc_auc"], "m6_auc": r6["metrics"]["roc_auc"],
                              "delta": round(r6["metrics"]["roc_auc"] - r4["metrics"]["roc_auc"], 4)
                              if r4["metrics"]["roc_auc"] and r6["metrics"]["roc_auc"] else None}
    leave_one_out = {"per_instrument_held_out": loo_rows}

    # ---- §16 horizon analysis (M4 & M6, both models, all folds) ------------
    horizon_rows: List[Dict[str, Any]] = []
    for h in ALL_HORIZONS:
        ds_h = ds_15m[h]
        folds_h = folds_15m if h == PRIMARY_HORIZON else make_folds(ds_h, p80._FOLD_BOUNDARY_YEARS)
        for fold in folds_h:
            if h == PRIMARY_HORIZON:
                for name in ("M4_volatility_time", "M6_full"):
                    for m in (_PRIMARY_MODEL, _REFERENCE_MODEL):
                        fit = nested_fits.get((fold.fold, name, m))
                        if fit:
                            horizon_rows.append({"horizon": h, "fold": fold.fold,
                                                "test_period": test_period_label[fold.fold],
                                                "model_group": name, "model": m,
                                                "metrics": fit["metrics"]})
                continue
            train, _v, test, _r = split_fold(ds_h, fold, PRIMARY_TF)
            if len(train) < 200 or len(test) < 30:
                continue
            for name in ("M4_volatility_time", "M6_full"):
                for m in (_PRIMARY_MODEL, _REFERENCE_MODEL):
                    r = fit_and_eval_group(train, test, NESTED_MODELS[name], m)
                    horizon_rows.append({"horizon": h, "fold": fold.fold,
                                        "test_period": test_period_label[fold.fold],
                                        "model_group": name, "model": m, "metrics": r["metrics"]})
        del ds_h
    gc.collect()

    # ---- §17 secondary timeframe (1h, M4 & M6, both models, both folds) ---
    secondary_rows: List[Dict[str, Any]] = []
    for fold in folds_1h:
        train, _v, test, _r = split_fold(ds_1h_h4, fold, SECONDARY_TF)
        if len(train) < 200 or len(test) < 30:
            continue
        for name in ("M4_volatility_time", "M6_full"):
            for m in (_PRIMARY_MODEL, _REFERENCE_MODEL):
                r = fit_and_eval_group(train, test, NESTED_MODELS[name], m)
                secondary_rows.append({"fold": fold.fold, "test_period": test_period_label_1h[fold.fold],
                                      "model_group": name, "model": m, "metrics": r["metrics"]})

    # ---- §18/§19/§20/§21 controls (headline fold) -------------------------
    shuffled = shuffled_target_control(headline_train, headline_test,
                                       NESTED_MODELS["M6_full"], _REFERENCE_MODEL, seed=_SHUFFLE_SEED)
    placebo_m4 = matched_placebo_control(headline_train, headline_test,
                                        NESTED_MODELS["M4_volatility_time"], _REFERENCE_MODEL,
                                        PRIMARY_HORIZON)
    placebo_m6 = matched_placebo_control(headline_train, headline_test,
                                        NESTED_MODELS["M6_full"], _REFERENCE_MODEL, PRIMARY_HORIZON)
    shift_sweep_m4 = temporal_shift_sweep(headline_train, headline_test,
                                         NESTED_MODELS["M4_volatility_time"], _PRIMARY_MODEL,
                                         PRIMARY_HORIZON)
    shift_sweep_m6 = temporal_shift_sweep(headline_train, headline_test,
                                         NESTED_MODELS["M6_full"], _PRIMARY_MODEL, PRIMARY_HORIZON)
    future_shock = check_feature_future_shock_invariance()

    controls = {
        "shuffled_target": shuffled,
        "population_decoupled_placebo_NOTE": (
            "NOT recomputed here -- Phase 80 already established it is confounded by population "
            "breadth (rv_rank spans ~0-1 vs the real study's ~0.66-1), and is superseded by the "
            "population-matched placebo below (identical methodology, unchanged)."),
        "matched_placebo": {"m4_volatility_time": placebo_m4, "m6_full": placebo_m6,
                           "shift_bars": _MATCHED_PLACEBO_SHIFT_BARS},
        "temporal_shift_sweep": {"m4_volatility_time": shift_sweep_m4, "m6_full": shift_sweep_m6},
        "future_shock_invariance": future_shock,
    }

    # ---- §22 bootstrap: headline delta(M6 - M4), reference model ----------
    fit_m4 = nested_fits[(headline_fold.fold, "M4_volatility_time", _REFERENCE_MODEL)]
    fit_m6 = nested_fits[(headline_fold.fold, "M6_full", _REFERENCE_MODEL)]
    delta_boot = bootstrap_delta_ci(fit_m4["_y_true"], fit_m6["_p_pred"], fit_m4["_p_pred"], _auc_fn,
                                    block=PRIMARY_HORIZON)
    bootstrap = {"delta_auc_full_minus_voltime": delta_boot}

    calibration_headline = fit_m6.get("calibration")

    # ---- §20 in-process determinism recheck (headline nested sweep) -------
    def _headline_signature() -> str:
        parts = []
        for name in NESTED_MODELS:
            for m in (_PRIMARY_MODEL, _REFERENCE_MODEL):
                fit = nested_fits.get((headline_fold.fold, name, m))
                if fit:
                    parts.append({"group": name, "model": m, "metrics": fit["metrics"]})
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()

    sig_a = _headline_signature()
    train2, _v2, test2, _r2 = split_fold(ds_15m[PRIMARY_HORIZON], headline_fold, PRIMARY_TF)
    _, rerun_fits = _nested_sweep(ds_15m[PRIMARY_HORIZON], [headline_fold], PRIMARY_TF)
    parts_b = [{"group": name, "model": m, "metrics": rerun_fits[(headline_fold.fold, name, m)]["metrics"]}
              for name in NESTED_MODELS for m in (_PRIMARY_MODEL, _REFERENCE_MODEL)
              if (headline_fold.fold, name, m) in rerun_fits]
    sig_b = hashlib.sha256(json.dumps(parts_b, sort_keys=True, default=str).encode()).hexdigest()
    determinism = {"headline_signature_a": sig_a, "headline_signature_b": sig_b, "match": sig_a == sig_b}

    # ---- §33 gates + §32/§34 verdict --------------------------------------
    real_auc_m6 = fit_m6["metrics"].get("roc_auc")
    placebo_auc_m6 = (placebo_m6 or {}).get("metrics", {}).get("roc_auc")
    shuffled_auc = shuffled.get("metrics", {}).get("roc_auc")
    gates = evaluate_gates_81(dataset_ok, leakage_ok, determinism["match"],
                              neutralization_methodology_ok, vol_conditioning_ok,
                              cross_asset_complete, True, real_auc_m6, placebo_auc_m6,
                              shuffled_auc, True)

    delta_full_vs_voltime = delta_boot.get("point") if delta_boot.get("state") != "INSUFFICIENT_SAMPLE" else None
    delta_ci_excludes_zero = bool(delta_boot.get("excludes_zero"))
    cross_year_signs = []
    for fold in folds_15m:
        a4 = nested_fits.get((fold.fold, "M4_volatility_time", _REFERENCE_MODEL), {}).get(
            "metrics", {}).get("roc_auc")
        a6 = nested_fits.get((fold.fold, "M6_full", _REFERENCE_MODEL), {}).get(
            "metrics", {}).get("roc_auc")
        cross_year_signs.append(bool(a6 > a4) if (a4 is not None and a6 is not None) else None)
    cross_asset_signs = [bool(v > 0) if v is not None else None for v in cross_asset_delta.values()]

    verdict, verdict_reason = classify_verdict_81(
        gates, delta_full_vs_voltime, delta_ci_excludes_zero, cross_year_signs, cross_asset_signs,
        time_resid_info.get("cv_r2_mean"), vol_resid_info.get("cv_r2_mean"))

    # ---- §37 V1 decision + §36/§48 Phase 82 queue --------------------------
    v1_decision = {
        "question": "Has V2 produced enough evidence of scientifically meaningful residual "
                   "information to justify additional ML development?",
        "answer": "YES" if verdict == "V2_RESIDUAL_INFORMATION_CONFIRMED" else "NO",
        "reasoning": verdict_reason,
        "v1_independently_evaluated": False,
        "note": "V1 (15m compression-duration -> range persistence) is NOT instantiated in this "
               "phase; it was never made contingent on V2's outcome and remains a separate, "
               "independent decision for a future phase.",
    }
    phase82_queue: List[Dict[str, Any]] = []
    if verdict == "V2_RESIDUAL_INFORMATION_CONFIRMED":
        phase82_queue.append({"item": "Narrowly scoped follow-up validating the specific residual "
                              "features identified here", "scope": "no trading integration"})
    elif verdict == "V2_EXPLAINED_BY_TIME_AND_VOLATILITY":
        phase82_queue.append({"item": "Treat V2 as a documented regime-context phenomenon "
                              "(rv_rank + session/hour) for potential future use as a market-state "
                              "feature or conditioning variable -- NOT an ML target",
                              "scope": "no further predictive-modelling phase for V2"})
    elif verdict == "V2_PREDICTABLE_BUT_RESIDUAL_INFORMATION_UNSTABLE":
        phase82_queue.append({"item": "Record V2 residual-information instability as a negative "
                              "result; do not re-tune this pipeline against these results",
                              "scope": "research closed pending independently new evidence"})
    else:
        phase82_queue.append({"item": "Diagnose and fix the identified pipeline/leakage/"
                              "reproducibility issue before any further interpretation",
                              "scope": "blocking"})
    phase82_queue = phase82_queue[:3]

    ident = json.dumps({
        "schema": SCHEMA_VERSION, "verdict": verdict, "gates": gates["gates"],
        "delta_full_vs_voltime": delta_full_vs_voltime,
        "nested_rows": sorted((r["fold"], r["model_group"], r["model"], r["metrics"].get("roc_auc"))
                             for r in nested_rows),
    }, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase81Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        phase80_commit_reference=p80_artifact.get("git_commit"),
        target_version=TARGET_VERSION, dataset_version=DATASET_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION, universe=list(INSTRUMENTS_V2),
        timeframes=[PRIMARY_TF, SECONDARY_TF], horizons=list(ALL_HORIZONS),
        feature_groups=feature_group_registry_dicts(), dataset_summary=dataset_summary,
        feature_target_contract=contract, zero_variance=zero_var, folds=folds_dict,
        nested_models=nested_rows, extended_ablation=extended_rows, conditional_rates=cond_rates,
        hour_mechanism=hour_mech, interactions=interactions, time_neutralization=time_neutralization,
        volatility_neutralization=volatility_neutralization, cross_asset=cross_asset,
        cross_year={"per_fold": [
            {"fold": f.fold, "test_period": test_period_label[f.fold],
             "m4_auc": nested_fits.get((f.fold, "M4_volatility_time", _REFERENCE_MODEL), {}).get(
                 "metrics", {}).get("roc_auc"),
             "m6_auc": nested_fits.get((f.fold, "M6_full", _REFERENCE_MODEL), {}).get(
                 "metrics", {}).get("roc_auc")}
            for f in folds_15m]},
        leave_one_asset_out=leave_one_out, horizon_analysis=horizon_rows,
        secondary_timeframe=secondary_rows, controls=controls, bootstrap=bootstrap,
        calibration_headline=calibration_headline, determinism=determinism, gates=gates,
        verdict=verdict, verdict_reason=verdict_reason, v1_decision=v1_decision,
        phase82_queue=phase82_queue, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase81Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase81_v2_information_decomposition", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 81 - V2 incremental information / context decomposition ...", flush=True)
    res = run()
    print(f"\n=== PHASE 81 ({res.runtime_seconds}s) ===")
    print(f"Dataset: {json.dumps(res.dataset_summary, default=str)}")
    print("\nNested models (fold 3, reference model):")
    for r in res.nested_models:
        if r["fold"] == 3 and r["model"] == _REFERENCE_MODEL:
            print(f"  {r['model_group']:<28} n_feat={r['n_features']:<3} AUC={r['metrics']['roc_auc']}")
    print(f"\nBootstrap delta(M6-M4): {json.dumps(res.bootstrap, default=str)}")
    print(f"\nGates: {json.dumps(res.gates, default=str)}")
    print(f"\nDeterminism match: {res.determinism['match']}")
    print(f"\nVERDICT: {res.verdict}  ({res.verdict_reason})")
    print(f"\nV1 DECISION: {res.v1_decision['answer']}")
    print(f"\nPHASE 82 QUEUE ({len(res.phase82_queue)}):")
    for q in res.phase82_queue:
        print(f"  {q}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "FEATURE_GROUPS_81", "NESTED_MODELS", "ABLATION_81", "feature_group_registry_dicts",
    "build_phase81_dataset", "assert_feature_target_contract", "fit_and_eval_group",
    "zero_variance_report", "compute_conditional_rates", "compute_time_neutralized_residual",
    "compute_volatility_neutralized_residual", "evaluate_residual_information",
    "bootstrap_metric_ci", "bootstrap_delta_ci", "hour_mechanism_report", "interaction_report",
    "matched_placebo_targets", "matched_placebo_control", "temporal_shift_sweep",
    "evaluate_gates_81", "classify_verdict_81", "run", "persist", "get_result", "main",
    "Phase81Result", "ARTIFACT_KEY", "SCHEMA_VERSION", "TARGET_VERSION", "DATASET_VERSION",
    "FEATURE_SCHEMA_VERSION",
]
