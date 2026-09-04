# -*- coding: utf-8 -*-
"""
Phase 82 — V1 15m Compression -> Expansion ML Pilot.

A research-INTEGRITY phase, not a strategy phase. Investigates V1 ONLY
(Phase 78/79's compression-duration -> range-expansion phenomenon), not V2
(closed in Phase 81 as `V2_EXPLAINED_BY_TIME_AND_VOLATILITY`).

CENTRAL QUESTION: does the duration of a volatility-compression episode
contain predictive information about subsequent range expansion BEYOND
ordinary volatility state, time/session structure, and recent price/range
conditions?

§1 CANONICAL DEFINITION AND A DOCUMENTED RESOLUTION OF AMBIGUITY
------------------------------------------------------------------
The V1 event/target are reused UNCHANGED from Phase 78/79:
  - compression threshold: ATR percentile rank (`atr_rank`, causal, trailing
    200-bar) <= 0.10 (`phase78_market_behavior_discovery_ii._COMPRESSION_RANK_THR`)
  - minimum run: 3 consecutive compressed bars
    (`_COMPRESSION_MIN_RUN`)
  - target: (forward h-bar sum of true range) / (atr_stable(event) * h) - 1
    -- atr_stable is the trailing-200-bar MEAN of ATR(14), never the
    event-time ATR (the bug class Phase 76/78 already fixed once). This is
    the RAW ratio: Phase 78/79's `study_range_expansion` additionally
    subtracts this SAME ratio's unconditional mean over the whole dev/oos
    slice ("baseline-centred") for AGGREGATE hypothesis testing -- a second,
    independently-discovered correction (§ future-shock test) established
    that this global, non-causal centering constant is not a valid PER-ROW
    ML label (see `_v1_targets`'s docstring for the full diagnosis), so the
    ML target here is the raw ratio, matching Phase 80's own precedent
    exactly (V2's ML target is the raw label, not Phase 78/79's
    baseline-centred aggregate "effect"). `baseline_mean` is still computed
    and stored as metadata for continuity-checking against Phase 78/79's
    own published numbers.
  - restricted to 15m only (Phase 79's `V1_TARGET_SPEC`, version
    "V1-target-v1"); NOT extended to 1h here either.
  - horizons: the unchanged FWD_HORIZONS = (1, 2, 4, 8) bars, h=4 headline.

A genuine ambiguity was found and is resolved here, not silently patched:
Phase 78's event BUILDER (`_b_compression_duration`) selects ONLY the bar
where `comp_run == min_run` (== 3) -- the FIRST bar of a qualifying streak.
Empirically, EVERY event under that literal definition therefore has
duration EXACTLY 3 (verified: `set(comp_run[event_idx]) == {3}`) -- an exact
structural analogue of Phase 81's V2 "current-state" degeneracy. Studying
"compression duration" as a variable (the master prompt's central request,
and the phenomenon's own name) is IMPOSSIBLE on that literal event set.

Resolution (documented, not silently chosen to flatter the result): Phase 82
uses TWO event populations, built from the SAME `comp_run` column with the
SAME threshold/min-run and NO other change:
  - CANONICAL (`build_canonical_v1_dataset`): `comp_run == 3` exactly, the
    literal Phase 78/79 population -- used ONLY to reproduce Phase 78/79's
    own aggregate numbers as a continuity/sanity check (§ tests).
  - DURATION-EXTENDED (`build_v1_dataset`, the PRIMARY dataset for this
    entire phase): `comp_run >= 3`, i.e. every bar that is itself part of a
    qualifying compression run, with `comp_run` (3, 4, 5, ... naturally
    decaying) serving as the genuinely variable "duration" feature this
    phase exists to study. The compression THRESHOLD, MINIMUM RUN, ATR
    DENOMINATOR, TARGET FORMULA and BASELINE-CENTERING are IDENTICAL between
    the two populations -- only which qualifying bars are counted as
    separate event rows changes. This is flagged as introducing WITHIN-
    STREAK event overlap (§ event overlap analysis) that the canonical
    single-shot population does not have.

No ML/DL library beyond `sklearn` (already a project dependency). Primary
model is Ridge (interpretable, deterministic, no convergence warnings);
RandomForestRegressor and HistGradientBoostingRegressor are secondary
reference models only, evaluated at the key comparisons.

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
from unittest import mock

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
import phase79_ml_target_integrity as p79
import phase80_ml_volatility_regime as p80
import phase81_v2_information_decomposition as p81
from phase76_event_study import FWD_HORIZONS, load_bars
from phase78_market_behavior_discovery_ii import (
    _COMPRESSION_MIN_RUN, _COMPRESSION_RANK_THR, INSTRUMENTS, augment,
)
from phase80_ml_volatility_regime import (
    Fold, RANDOM_SEED, _TF_SECONDS, make_folds, split_fold,
)
from phase81_v2_information_decomposition import bootstrap_delta_ci, bootstrap_metric_ci

SCHEMA_VERSION = "phase82.1"
ARTIFACT_KEY = "phase82_compression_expansion_ml_pilot"
TARGET_VERSION = p79.V1_TARGET_SPEC.version               # "V1-target-v1" -- unchanged
CANONICAL_DATASET_VERSION = "phase82-v1-canonical-v1"     # comp_run == 3 only (Phase78/79 literal)
EXTENDED_DATASET_VERSION = "phase82-v1-duration-extended-v1"  # comp_run >= 3 (this phase's primary)
FEATURE_SCHEMA_VERSION = "phase82-features-v1"

PRIMARY_TF = "15m"          # ONLY -- no 1h in this phase (§2 of the master prompt)
PRIMARY_HORIZON = 4
ALL_HORIZONS: Tuple[int, ...] = FWD_HORIZONS               # (1, 2, 4, 8), unchanged
INSTRUMENTS_V1: Tuple[str, ...] = INSTRUMENTS               # unchanged 6-instrument universe
_WARMUP = 200
_MAX_DURATION_FOR_FEATURE = 60      # a sanity cap on the raw continuous duration feature
                                    # (>=60 consecutive compressed 15m bars is >2.5 trading
                                    # days and vanishingly rare -- capped so one absurd streak
                                    # cannot dominate a linear model's scale; NOT a bin choice)
_DURATION_BIN_EDGES = (3, 4, 5, 6, 7, 10_000)      # predeclared: 3,4,5,6,"7+"
_DURATION_BIN_LABELS = ("3", "4", "5", "6", "7+")

_FOLD_BOUNDARY_YEARS = p80._FOLD_BOUNDARY_YEARS     # (2023, 2024, 2025) -- reused, unchanged
_MATCHED_PLACEBO_SHIFT_BARS = 200                   # reused Phase 80/81 default
_TEMPORAL_SHIFT_SWEEP: Tuple[int, ...] = (50, 100, 200, 500, 2000)
_GATE_H_MARGIN = 0.05        # AUC-scale margin doesn't apply to R2; see gate documentation below
_GATE_H_R2_MARGIN = 0.01     # reused proportionally: "material" R2 improvement margin
_SHUFFLE_SEED = 82001
_MIN_CELL_N = 100
_VOL_TERCILE_EDGES = (0.0, 1 / 3, 2 / 3, 1.0001)
_VOL_TERCILE_LABELS = ("low", "mid", "high")

_PRIMARY_MODEL = "ridge"
_REFERENCE_MODELS = ("random_forest", "hist_gradient_boosting")


# ==========================================================================
# §9 feature-group registry (regression-oriented; Group C bundles price +
# range + candle exactly as the master prompt's own §9 Group C describes)
# ==========================================================================
FEATURE_GROUPS_82: Dict[str, List[str]] = {
    "COMPRESSION": ["duration", "severity"],
    "VOLATILITY": ["rv", "rv_rank", "atr_ret"],
    "RANGE_PRICE": ["ret_1", "ret_4", "ret_8", "abs_ret_1", "tr_atr", "body_range_ratio",
                    "upper_wick_ratio", "lower_wick_ratio", "dist_from_roll_high",
                    "dist_from_roll_low"],
    "TIME": ["hour_sin", "hour_cos", "dow", "session_code"],
    "REGIME": ["regime_code"],
}

# §10/§39 nested model sequence (M0-M8, matching the master prompt's B0-B8 table)
NESTED_MODELS_82: Dict[str, List[str]] = {
    "M0_constant": [],
    "M1_volatility": FEATURE_GROUPS_82["VOLATILITY"],
    "M2_compression": FEATURE_GROUPS_82["COMPRESSION"],
    "M3_compression_volatility": FEATURE_GROUPS_82["COMPRESSION"] + FEATURE_GROUPS_82["VOLATILITY"],
    "M4_time": FEATURE_GROUPS_82["TIME"],
    "M5_volatility_time": FEATURE_GROUPS_82["VOLATILITY"] + FEATURE_GROUPS_82["TIME"],
    "M6_compression_volatility_time": (FEATURE_GROUPS_82["COMPRESSION"]
                                       + FEATURE_GROUPS_82["VOLATILITY"] + FEATURE_GROUPS_82["TIME"]),
    "M7_plus_range_price": (FEATURE_GROUPS_82["COMPRESSION"] + FEATURE_GROUPS_82["VOLATILITY"]
                            + FEATURE_GROUPS_82["TIME"] + FEATURE_GROUPS_82["RANGE_PRICE"]),
    "M8_full": (FEATURE_GROUPS_82["COMPRESSION"] + FEATURE_GROUPS_82["VOLATILITY"]
               + FEATURE_GROUPS_82["TIME"] + FEATURE_GROUPS_82["RANGE_PRICE"]
               + FEATURE_GROUPS_82["REGIME"]),
}
# §43 predeclared extended ablation (A-H); most reuse the M-sequence's exact
# column sets (not re-fit) -- only letters with no M-equivalent are new.
ABLATION_82: Dict[str, List[str]] = {
    "A_volatility_only": NESTED_MODELS_82["M1_volatility"],
    "B_compression_only": NESTED_MODELS_82["M2_compression"],
    "C_time_only": NESTED_MODELS_82["M4_time"],
    "D_volatility_time": NESTED_MODELS_82["M5_volatility_time"],
    "E_compression_volatility": NESTED_MODELS_82["M3_compression_volatility"],
    "F_compression_volatility_time": NESTED_MODELS_82["M6_compression_volatility_time"],
    "G_plus_price_range": NESTED_MODELS_82["M7_plus_range_price"],
    "H_full": NESTED_MODELS_82["M8_full"],
}

# §47/§48 pre-registered hypotheses (frozen before any result was viewed)
H1_PRIMARY = ("Compression duration provides incremental predictive information about "
             "subsequent range expansion beyond current volatility and deterministic "
             "time/session structure (M6 vs M5, out-of-sample).")
H0_NULL = ("Compression duration provides no meaningful incremental predictive information "
          "beyond current volatility and time/session structure.")
SECONDARY_HYPOTHESES = {
    "H2_monotonic_or_systematic": "The duration -> expansion relationship is monotonic or systematically nonlinear.",
    "H3_survives_range_conditioning": "The relationship survives conditioning on recent range.",
    "H4_generalizes_cross_asset": "The relationship generalizes across instruments.",
    "H5_generalizes_cross_year": "The relationship generalizes across years.",
    "H6_ml_not_much_beyond_interpretable": "ML does not produce materially more information than "
                                          "interpretable duration/volatility/time models unless "
                                          "residual structure exists.",
}


def feature_group_registry_dicts() -> Dict[str, Any]:
    return {"groups": FEATURE_GROUPS_82, "nested_models": NESTED_MODELS_82, "ablation": ABLATION_82,
           "primary_hypothesis": H1_PRIMARY, "null_hypothesis": H0_NULL,
           "secondary_hypotheses": SECONDARY_HYPOTHESES}


# ==========================================================================
# §6 causal feature builder (all values at bar i use only data through i)
# ==========================================================================
_REGIME_CODE = {"TRENDING": 2.0, "MIXED": 1.0, "RANGING": 0.0}
_SESSION_CODE = {"TOKYO": 0.0, "LONDON": 1.0, "LONDON_NY_OVERLAP": 2.0,
                "NEW_YORK": 3.0, "LATE_US": 4.0}


def _build_features_82(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].to_numpy(float)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    ret = df["ret"].to_numpy(float)
    n = len(df)

    def _lag_ret(k: int) -> np.ndarray:
        out = np.full(n, np.nan)
        out[k:] = np.log(c[k:] / c[:-k])
        return out

    comp_run = df["comp_run"].to_numpy(float)
    duration = np.clip(comp_run, 0, _MAX_DURATION_FOR_FEATURE)
    atr_rank = df["atr_rank"].to_numpy(float)
    severity = _COMPRESSION_RANK_THR - atr_rank   # positive = deeper compression, causal transform

    rng = h - lo
    rng_safe = np.where(rng > 1e-12, rng, np.nan)
    body_range_ratio = np.abs(c - o) / rng_safe
    upper_wick_ratio = (h - np.maximum(o, c)) / rng_safe
    lower_wick_ratio = (np.minimum(o, c) - lo) / rng_safe

    roll_h = df["roll_h20"].to_numpy(float)      # already causal (shift(1) in augment())
    roll_l = df["roll_l20"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    atr_safe = np.where(atr > 0, atr, np.nan)
    dist_from_roll_high = (roll_h - c) / atr_safe
    dist_from_roll_low = (c - roll_l) / atr_safe

    regime_code = np.array([_REGIME_CODE.get(r, 1.0) for r in df["regime"].to_numpy()], float)
    session_code = np.array([_SESSION_CODE.get(s, 4.0) for s in df["session"].to_numpy()], float)
    dow = np.array([d.weekday() for d in df["date"].to_numpy()], float)
    hour = df["hour"].to_numpy(float)

    return pd.DataFrame({
        "duration": duration, "severity": severity,
        "rv": df["rv"].to_numpy(float), "rv_rank": df["rv_rank"].to_numpy(float),
        "atr_ret": df["atr_ret"].to_numpy(float),
        "ret_1": ret, "ret_4": _lag_ret(4), "ret_8": _lag_ret(8), "abs_ret_1": np.abs(ret),
        "tr_atr": df["tr_atr"].to_numpy(float), "body_range_ratio": body_range_ratio,
        "upper_wick_ratio": upper_wick_ratio, "lower_wick_ratio": lower_wick_ratio,
        "dist_from_roll_high": dist_from_roll_high, "dist_from_roll_low": dist_from_roll_low,
        "hour_sin": np.sin(2 * np.pi * hour / 24.0), "hour_cos": np.cos(2 * np.pi * hour / 24.0),
        "dow": dow, "session_code": session_code, "regime_code": regime_code,
    })


# ==========================================================================
# §1/§3/§6 event indices -- both populations, from the SAME comp_run column
# ==========================================================================
def canonical_event_indices(df: pd.DataFrame) -> np.ndarray:
    """EXACT Phase 78/79 event: comp_run == min_run (fires once per streak)."""
    return p78._b_compression_duration(df)[0]


def extended_event_indices(df: pd.DataFrame, min_run: int = _COMPRESSION_MIN_RUN) -> np.ndarray:
    """§1 documented resolution: every bar with comp_run >= min_run -- the
    primary population for this phase's duration dose-response study."""
    run = df["comp_run"].to_numpy(int)
    idx = np.where(run >= min_run)[0]
    return idx[idx >= _WARMUP]


# ==========================================================================
# §3 target -- the EXACT Phase 78 study_range_expansion formula, per-row
# ==========================================================================
def _v1_targets(df: pd.DataFrame, idx: np.ndarray, horizon: int
                ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Returns (valid_idx, target_end_idx, target_value_array, baseline_mean).

    IMPORTANT CORRECTION (found via the future-shock invariance test, §34,
    and documented rather than silently patched): Phase 78's
    ``study_range_expansion`` centres its reported EFFECT by subtracting a
    ``baseline_mean`` computed ONCE, non-causally, over the ENTIRE dev/oos
    slice being studied (every valid bar, including ones far in the future
    of any individual event). That is a legitimate, already-frozen
    convention for ONE-TIME AGGREGATE HYPOTHESIS TESTING on a fixed
    historical sample (Phase 76/78/79's whole point), but it makes every
    single row's "target" value depend on a global constant that shifts
    if ANY bar anywhere in the slice changes -- concretely, inserting a
    future shock changed the reported target for events far BEFORE the
    shock, even though every FEATURE and every MODEL PREDICTION at those
    events stayed byte-identical (verified). That is not a forecasting
    leak (no feature or prediction is affected) but it does mean the
    baseline-centred value is not a valid PER-ROW ML LABEL for a live-style
    walk-forward pilot.

    Resolution, matching Phase 80's own precedent exactly (V2's ML target
    is the RAW label ``rv_rank[i+h] > 0.66``, NOT Phase 78/79's baseline-
    centred "effect"): Phase 82's ML target is the RAW expansion ratio,
    with NO global centering applied. ``baseline_mean`` is still computed
    and returned (for continuity-checking against Phase 78/79's own
    published aggregate numbers, §ambiguity-resolution tests), but it is
    metadata, not part of the label. The standard OOS-R^2 methodology
    already used throughout (§21, against the TRAIN mean) supplies the
    "beat the average" comparison this pilot needs, without a non-causal
    global constant baked into the label itself."""
    tr = df["tr"].to_numpy(float)
    atr_stable = df["atr_stable"].to_numpy(float)
    n = len(df)
    idx = np.asarray(idx, int)
    ok = (idx >= 0) & (idx < n) & np.isfinite(atr_stable[np.clip(idx, 0, n - 1)]) \
        & (atr_stable[np.clip(idx, 0, n - 1)] > 0)
    idx = idx[ok]
    j = idx + horizon
    valid = j < n
    idx, j = idx[valid], j[valid]
    csum = np.concatenate([[0.0], np.cumsum(tr)])
    fut = csum[j + 1] - csum[idx + 1]
    ratio = fut / (atr_stable[idx] * horizon) - 1.0

    base_idx = np.arange(n - horizon)
    base_ok = np.isfinite(atr_stable[base_idx]) & (atr_stable[base_idx] > 0)
    bi = base_idx[base_ok]
    base_fut = csum[bi + horizon + 1] - csum[bi + 1]
    base_ratio = base_fut / (atr_stable[bi] * horizon) - 1.0
    base_ratio = base_ratio[np.isfinite(base_ratio)]
    baseline_mean = float(np.mean(base_ratio)) if len(base_ratio) else 0.0

    finite = np.isfinite(ratio)
    idx, j, ratio = idx[finite], j[finite], ratio[finite]
    target = ratio    # RAW ratio -- see docstring; NOT baseline-centred
    return idx, j, target, baseline_mean


def _assemble_dataset(instrument: str, tf: str, horizon: int, event_fn, dataset_version: str
                      ) -> pd.DataFrame:
    df = load_bars(instrument, tf)
    if df.empty or len(df) < 2000:
        return pd.DataFrame()
    df = augment(df, tf)
    feats_all = _build_features_82(df)
    idx0 = event_fn(df)
    idx, j, target, baseline_mean = _v1_targets(df, idx0, horizon)
    if len(idx) == 0:
        return pd.DataFrame()
    feat_rows = feats_all.iloc[idx].reset_index(drop=True)
    finite_mask = np.isfinite(feat_rows.to_numpy(float)).all(axis=1)
    idx, j, target = idx[finite_mask], j[finite_mask], target[finite_mask]
    feat_rows = feat_rows.loc[finite_mask].reset_index(drop=True)
    if len(idx) == 0:
        return pd.DataFrame()
    tf_sec = _TF_SECONDS[tf]
    open_ts = df["t"].to_numpy(np.int64)
    pred_ts = pd.to_datetime(open_ts[idx].astype(np.int64) + tf_sec, unit="s", utc=True)
    targ_end_ts = pd.to_datetime(open_ts[j].astype(np.int64) + tf_sec, unit="s", utc=True)
    out = pd.DataFrame({
        "instrument": instrument, "timeframe": tf, "horizon_bars": horizon,
        "event_idx": idx, "target_idx": j, "prediction_timestamp": pred_ts,
        "target_end_timestamp": targ_end_ts, "target": target,
        "baseline_mean": baseline_mean, "dataset_version": dataset_version,
        "target_version": TARGET_VERSION, "feature_schema_version": FEATURE_SCHEMA_VERSION,
    })
    return pd.concat([out, feat_rows.add_prefix("feat__")], axis=1)


def build_canonical_v1_dataset(instrument: str, tf: str = PRIMARY_TF,
                               horizon: int = PRIMARY_HORIZON) -> pd.DataFrame:
    return _assemble_dataset(instrument, tf, horizon, canonical_event_indices, CANONICAL_DATASET_VERSION)


def build_v1_dataset(instrument: str, tf: str = PRIMARY_TF, horizon: int = PRIMARY_HORIZON
                     ) -> pd.DataFrame:
    """The PRIMARY dataset for this phase (duration-extended population, §1)."""
    return _assemble_dataset(instrument, tf, horizon, extended_event_indices, EXTENDED_DATASET_VERSION)


_INSTRUMENT_CODE = {inst: float(k) for k, inst in enumerate(INSTRUMENTS_V1)}


def build_pooled_v1_dataset(horizon: int = PRIMARY_HORIZON, canonical: bool = False,
                            instruments: Tuple[str, ...] = INSTRUMENTS_V1) -> pd.DataFrame:
    builder = build_canonical_v1_dataset if canonical else build_v1_dataset
    frames = [d for inst in instruments if not (d := builder(inst, PRIMARY_TF, horizon)).empty]
    if not frames:
        return pd.DataFrame()
    pooled = pd.concat(frames, ignore_index=True)
    pooled["feat__instrument_code"] = pooled["instrument"].map(_INSTRUMENT_CODE)
    return pooled.sort_values("prediction_timestamp").reset_index(drop=True)


def assert_feature_target_contract(dataset: pd.DataFrame) -> Dict[str, Any]:
    return p80.assert_feature_target_contract(dataset)


# ==========================================================================
# §35/§36/§37 leakage / event-selection / censoring audits
# ==========================================================================
def event_selection_audit(df: pd.DataFrame, event_fn) -> Dict[str, Any]:
    """§36 -- the event's own construction must use ONLY comp_run (itself
    purely backward-looking, §7 of Phase78's augment) and NOTHING forward.
    Verified functionally: truncating the series strictly AFTER an event
    bar must not change whether that bar qualifies as an event."""
    idx_full = event_fn(df)
    cut = len(df) - 50
    idx_truncated = event_fn(df.iloc[:cut].reset_index(drop=True))
    idx_full_before_cut = idx_full[idx_full < cut - 10]     # avoid the boundary itself
    idx_trunc_before_cut = idx_truncated[idx_truncated < cut - 10]
    return {"n_events_full_before_cut": int(len(idx_full_before_cut)),
           "n_events_truncated_before_cut": int(len(idx_trunc_before_cut)),
           "identical": bool(np.array_equal(idx_full_before_cut, idx_trunc_before_cut))}


def censored_event_audit(df: pd.DataFrame, event_fn, horizon: int) -> Dict[str, Any]:
    """§37 -- events whose forward window would run past the series end must
    be dropped, never imputed. Counts how many were dropped for this reason."""
    idx0 = event_fn(df)
    n = len(df)
    censored = idx0[(idx0 + horizon) >= n]
    return {"n_events_before_censor_check": int(len(idx0)),
           "n_censored_dropped": int(len(censored)),
           "frac_censored": round(len(censored) / max(1, len(idx0)), 5)}


def event_overlap_audit(idx: np.ndarray, horizon: int) -> Dict[str, Any]:
    """§38 -- quantify clustering/overlap. The duration-EXTENDED population
    (§1) is explicitly expected to show heavy overlap (consecutive bars of
    the SAME streak); the canonical population should not."""
    idx = np.sort(np.asarray(idx, int))
    if len(idx) < 2:
        return {"n_events": int(len(idx))}
    gaps = np.diff(idx).astype(float)
    avg_gap = float(np.mean(gaps))
    overlap_frac = float(np.mean(gaps < horizon))
    eff_spacing = max(avg_gap, float(horizon))
    effective_n = len(idx) * (avg_gap / eff_spacing) if avg_gap > 0 else float(len(idx))
    return {"n_events": int(len(idx)), "avg_gap_bars": round(avg_gap, 3),
           "pct_neighboring_pairs_overlapping": round(overlap_frac, 4),
           "effective_n_estimate": round(effective_n, 1),
           "effective_n_ratio": round(effective_n / len(idx), 4)}


# ==========================================================================
# §21/§44 regression metrics -- OOS R^2 defined against the TRAIN mean (not
# the test set's own mean, which would itself be a mild look-ahead into the
# test set's target distribution)
# ==========================================================================
def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray, train_mean: float
                               ) -> Dict[str, Any]:
    y, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    n = len(y)
    resid = y - p
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - train_mean) ** 2))
    oos_r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    mae = float(mean_absolute_error(y, p))
    rmse = float(np.sqrt(mean_squared_error(y, p)))
    if n >= 3 and np.std(y) > 1e-12 and np.std(p) > 1e-12 and len(np.unique(p)) > 1:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            spearman = float(pd.Series(y).corr(pd.Series(p), method="spearman"))
        if np.isnan(spearman):
            spearman = None
    else:
        spearman = None
    return {"n": int(n), "oos_r2": round(oos_r2, 5), "mae": round(mae, 5), "rmse": round(rmse, 5),
           "spearman": round(spearman, 4) if spearman is not None else None,
           "mean_actual": round(float(np.mean(y)), 5), "mean_predicted": round(float(np.mean(p)), 5),
           "resid_mean": round(float(np.mean(resid)), 5), "resid_std": round(float(np.std(resid)), 5)}


def error_by_prediction_decile(y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10
                               ) -> List[Dict[str, Any]]:
    """§44 regression-analog of a calibration/reliability table: within each
    predicted-value decile, does the mean ACTUAL target track the mean
    PREDICTED value?"""
    y, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    order = np.argsort(p)
    y, p = y[order], p[order]
    n = len(y)
    edges = np.linspace(0, n, n_bins + 1).astype(int)
    rows = []
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        if hi <= lo:
            continue
        rows.append({"bin": b, "n": int(hi - lo), "mean_predicted": round(float(p[lo:hi].mean()), 5),
                    "mean_actual": round(float(y[lo:hi].mean()), 5)})
    return rows


def _r2_metric_fn(train_mean: float):
    def _fn(y, p):
        y, p = np.asarray(y, float), np.asarray(p, float)
        ss_tot = float(np.sum((y - train_mean) ** 2))
        if ss_tot <= 0:
            return 0.0
        return 1.0 - float(np.sum((y - p) ** 2)) / ss_tot
    return _fn


# ==========================================================================
# §19 models -- Ridge primary (interpretable), RF/HGB secondary reference
# ==========================================================================
def _make_models_82() -> Dict[str, Any]:
    return {
        "ridge": Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0, random_state=RANDOM_SEED))]),
        "random_forest": RandomForestRegressor(n_estimators=200, max_depth=8, min_samples_leaf=20,
                                               random_state=RANDOM_SEED, n_jobs=-1),
        "hist_gradient_boosting": HistGradientBoostingRegressor(max_depth=6, max_iter=150,
                                                                 random_state=RANDOM_SEED),
    }


def fit_and_eval_82(train: pd.DataFrame, test: pd.DataFrame, features: List[str],
                    model_name: str = _PRIMARY_MODEL) -> Dict[str, Any]:
    train_mean = float(train["target"].mean())
    if not features:
        p_pred = np.full(len(test), train_mean)
        y_true = test["target"].to_numpy(float)
        return {"model": "constant", "features": [], "n_train": len(train),
               "metrics": compute_regression_metrics(y_true, p_pred, train_mean),
               "coefficients": None, "_p_pred": p_pred, "_y_true": y_true, "train_mean": train_mean}
    cols = [f"feat__{f}" for f in features]
    Xtr = train[cols].to_numpy(float)
    ytr = train["target"].to_numpy(float)
    Xte = test[cols].to_numpy(float)
    yte = test["target"].to_numpy(float)
    model = _make_models_82()[model_name]
    model.fit(Xtr, ytr)
    p_pred = model.predict(Xte)
    coefs = None
    if model_name == "ridge":
        reg = model.named_steps["reg"]
        coefs = {f: round(float(c), 6) for f, c in zip(features, reg.coef_)}
        coefs["_intercept"] = round(float(reg.intercept_), 6)
    return {"model": model_name, "features": features, "n_train": len(train),
           "metrics": compute_regression_metrics(yte, p_pred, train_mean),
           "error_deciles": error_by_prediction_decile(yte, p_pred),
           "coefficients": coefs, "_p_pred": p_pred, "_y_true": yte, "_fitted_model": model,
           "train_mean": train_mean}


def zero_variance_report(df: pd.DataFrame, features: List[str]) -> Dict[str, bool]:
    return {f: bool(df[f"feat__{f}"].nunique(dropna=True) <= 1) for f in features}


# ==========================================================================
# §12/§13 duration distribution + dose-response (descriptive, full dataset)
# ==========================================================================
def compute_duration_statistics(ds: pd.DataFrame) -> Dict[str, Any]:
    dur = ds["feat__duration"].to_numpy(float)
    vals, counts = np.unique(dur, return_counts=True)
    return {"n_events": int(len(ds)), "min": float(dur.min()), "max": float(dur.max()),
           "mean": round(float(dur.mean()), 3), "median": float(np.median(dur)),
           "distribution": {int(v): int(c) for v, c in zip(vals, counts)}}


def _duration_bucket(duration: np.ndarray) -> pd.Categorical:
    return pd.cut(duration, bins=_DURATION_BIN_EDGES, labels=_DURATION_BIN_LABELS,
                 right=False, include_lowest=True)


def compute_duration_dose_response(ds: pd.DataFrame, min_n: int = _MIN_CELL_N) -> Dict[str, Any]:
    bucket = _duration_bucket(ds["feat__duration"].to_numpy(float))
    g = ds.assign(_bucket=bucket).groupby("_bucket", observed=True)["target"]
    out = {}
    for label, series in g:
        if len(series) < min_n:
            continue
        bs = p76.block_bootstrap(series.to_numpy(float), block=int(ds["horizon_bars"].iloc[0]))
        out[str(label)] = {"n": int(len(series)), "mean": round(float(series.mean()), 5),
                          "median": round(float(series.median()), 5),
                          "q25": round(float(series.quantile(0.25)), 5),
                          "q75": round(float(series.quantile(0.75)), 5),
                          "bootstrap_ci": [bs.get("ci_lower"), bs.get("ci_upper")],
                          "bootstrap_verdict": bs.get("verdict")}
    means = [v["mean"] for v in out.values()]
    monotonic_decreasing = bool(means == sorted(means, reverse=True)) if len(means) >= 2 else None
    monotonic_increasing = bool(means == sorted(means)) if len(means) >= 2 else None
    return {"by_duration_bucket": out,
           "monotonic_increasing": monotonic_increasing, "monotonic_decreasing": monotonic_decreasing}


def conditional_dose_response(ds: pd.DataFrame, condition: pd.Series, min_n: int = _MIN_CELL_N
                              ) -> Dict[str, Any]:
    """Generic E[target | condition] with N (§15/§16/§17)."""
    g = ds.assign(_c=condition).groupby("_c", observed=True)["target"].agg(["mean", "median", "count"])
    return {str(k): {"mean": round(float(v["mean"]), 5), "median": round(float(v["median"]), 5),
                    "n": int(v["count"])} for k, v in g.iterrows() if v["count"] >= min_n}


def duration_by_condition(ds: pd.DataFrame, condition: pd.Series, min_n: int = _MIN_CELL_N
                          ) -> Dict[str, Any]:
    g = ds.assign(_c=condition)["feat__duration"].groupby(condition, observed=True).agg(["mean", "count"])
    return {str(k): {"mean_duration": round(float(v["mean"]), 3), "n": int(v["count"])}
           for k, v in g.iterrows() if v["count"] >= min_n}


def volatility_tercile(ds: pd.DataFrame) -> pd.Series:
    return pd.cut(ds["feat__rv_rank"].to_numpy(float), bins=_VOL_TERCILE_EDGES,
                 labels=_VOL_TERCILE_LABELS, right=False, include_lowest=True)


def session_label(ds: pd.DataFrame) -> pd.Series:
    inv = {v: k for k, v in _SESSION_CODE.items()}
    return ds["feat__session_code"].map(inv)


# ==========================================================================
# §14 severity vs duration decorrelation
# ==========================================================================
def duration_severity_decorrelation(ds: pd.DataFrame) -> Dict[str, Any]:
    dur = ds["feat__duration"].to_numpy(float)
    sev = ds["feat__severity"].to_numpy(float)
    corr = float(np.corrcoef(dur, sev)[0, 1]) if len(ds) > 2 else None
    return {"pearson_corr_duration_severity": round(corr, 4) if corr is not None else None}


# ==========================================================================
# §40/§41 residualization against context, train-only
# ==========================================================================
def compute_context_residual(train: pd.DataFrame, eval_df: pd.DataFrame, context_features: List[str]
                             ) -> Dict[str, Any]:
    cols = [f"feat__{f}" for f in context_features]
    model = Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0, random_state=RANDOM_SEED))])
    model.fit(train[cols].to_numpy(float), train["target"].to_numpy(float))
    pred = model.predict(eval_df[cols].to_numpy(float))
    residual = eval_df["target"].to_numpy(float) - pred
    return {"context_features": context_features, "residual": residual,
           "residual_mean": round(float(np.mean(residual)), 6),
           "residual_std": round(float(np.std(residual)), 6)}


def evaluate_residual_information(residual: np.ndarray, candidate_features: pd.DataFrame) -> Dict[str, Any]:
    X = candidate_features.to_numpy(float)
    y = np.asarray(residual, float)
    finite = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X, y = X[finite], y[finite]
    if len(y) < 200:
        return {"state": "INSUFFICIENT_SAMPLE"}
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
# §31 shuffled-target control
# ==========================================================================
def shuffled_target_control(train: pd.DataFrame, test: pd.DataFrame, features: List[str],
                            model_name: str, seed: int = _SHUFFLE_SEED) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    train_shuf = train.copy()
    train_shuf["target"] = rng.permutation(train_shuf["target"].to_numpy())
    r = fit_and_eval_82(train_shuf, test, features, model_name)
    return {"model": model_name, "metrics": r["metrics"]}


# ==========================================================================
# §32/§33 population-matched placebo + temporal-shift sweep. Same
# methodology Phase 80/81 corrected and validated: identical feature rows,
# target relabelled using the outcome ``shift_bars`` further into the
# future -- decouples the true horizon timing while holding the evaluated
# population exactly fixed. A small per-instrument bar cache avoids
# reloading/re-augmenting on every shift value.
# ==========================================================================
_BAR_CACHE_82: Dict[Tuple[str, str], pd.DataFrame] = {}


def _clear_bar_cache_82() -> None:
    _BAR_CACHE_82.clear()


def _get_augmented_bars(instrument: str, tf: str) -> pd.DataFrame:
    key = (instrument, tf)
    if key not in _BAR_CACHE_82:
        _BAR_CACHE_82[key] = augment(load_bars(instrument, tf), tf)
    return _BAR_CACHE_82[key]


def matched_placebo_targets(df_subset: pd.DataFrame, horizon: int,
                            shift_bars: int = _MATCHED_PLACEBO_SHIFT_BARS) -> np.ndarray:
    """RAW ratio (no baseline centering, matching the corrected ``_v1_targets``
    convention, §3 docstring) computed at ``event_idx + shift_bars`` instead
    of ``event_idx`` -- decouples the true horizon timing while holding the
    evaluated feature population exactly fixed."""
    tf = df_subset["timeframe"].iloc[0] if "timeframe" in df_subset.columns else PRIMARY_TF
    out = np.full(len(df_subset), np.nan)
    for inst in df_subset["instrument"].unique():
        bars = _get_augmented_bars(inst, tf)
        tr = bars["tr"].to_numpy(float)
        atr_stable = bars["atr_stable"].to_numpy(float)
        n = len(bars)
        csum = np.concatenate([[0.0], np.cumsum(tr)])
        m = (df_subset["instrument"] == inst).to_numpy()
        idxs = df_subset.loc[m, "event_idx"].to_numpy() + shift_bars
        j = idxs + horizon
        valid = (j < n) & (idxs < n) & (idxs >= 0) & np.isfinite(atr_stable[np.clip(idxs, 0, n - 1)]) \
            & (atr_stable[np.clip(idxs, 0, n - 1)] > 0)
        vals = np.full(len(idxs), np.nan)
        fut = csum[j[valid] + 1] - csum[idxs[valid] + 1]
        vals[valid] = fut / (atr_stable[idxs[valid]] * horizon) - 1.0
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
    r = fit_and_eval_82(train2, test2, features, model_name)
    return {"shift_bars": shift_bars, "metrics": r["metrics"]}


def temporal_shift_sweep(train: pd.DataFrame, test: pd.DataFrame, features: List[str],
                         model_name: str, horizon: int,
                         shifts: Tuple[int, ...] = _TEMPORAL_SHIFT_SWEEP) -> List[Dict[str, Any]]:
    out = []
    for s in shifts:
        r = matched_placebo_control(train, test, features, model_name, horizon, shift_bars=s)
        if r:
            out.append(r)
    return out


# ==========================================================================
# §34 future-shock invariance (V1-specific: uses the duration-extended event
# builder and the true-range/atr_stable target, not V2's rv_rank formula)
# ==========================================================================
def _synthetic_candles(n: int, seed: int, tf_sec: int = 900, t0: int = 1_650_000_000
                       ) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    return [{"time": t0 + i * tf_sec, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": 100.0, "source": "mt5"} for i in range(n)]


def _dataset_from_rows(rows: List[Dict[str, Any]], tf: str, horizon: int, instrument: str = "SYN"
                       ) -> pd.DataFrame:
    with mock.patch.object(p76.store, "get_candles", lambda *_a, **_k: rows):
        return build_v1_dataset(instrument, tf, horizon)


def check_future_shock_invariance(tf: str = "15m", n: int = 4000, seed: int = 401,
                                  cutoff: int = 3200, shock_mult: float = 50.0,
                                  horizon: int = 4) -> Dict[str, Any]:
    rows = _synthetic_candles(n, seed)
    ds_a = _dataset_from_rows(rows, tf, horizon)
    shock_i = cutoff + 5
    rows_b = [dict(r) for r in rows]
    rows_b[shock_i]["high"] *= shock_mult
    rows_b[shock_i]["low"] /= shock_mult
    ds_b = _dataset_from_rows(rows_b, tf, horizon)

    common_a = ds_a[ds_a["event_idx"] < cutoff]
    common_b = ds_b[ds_b["event_idx"] < cutoff]
    merged = common_a.merge(common_b, on="event_idx", suffixes=("_a", "_b"))
    feature_names = list(FEATURE_GROUPS_82["COMPRESSION"] + FEATURE_GROUPS_82["VOLATILITY"]
                         + FEATURE_GROUPS_82["RANGE_PRICE"] + FEATURE_GROUPS_82["TIME"]
                         + FEATURE_GROUPS_82["REGIME"])
    feats_equal = True
    for f in feature_names:
        a = merged[f"feat__{f}_a"].to_numpy()
        b = merged[f"feat__{f}_b"].to_numpy()
        if not np.allclose(np.nan_to_num(a, nan=-9.9e30), np.nan_to_num(b, nan=-9.9e30), rtol=0, atol=1e-9):
            feats_equal = False
    targets_equal = bool(np.allclose(merged["target_a"].to_numpy(), merged["target_b"].to_numpy(),
                                     rtol=0, atol=1e-9))
    pred_equal = True
    if len(merged) >= 30:
        model = _make_models_82()["ridge"]
        cols = [f"feat__{f}" for f in feature_names]
        model.fit(common_a[cols].to_numpy(float), common_a["target"].to_numpy(float))
        pa = model.predict(merged[[f"feat__{f}_a" for f in feature_names]].to_numpy(float))
        pb = model.predict(merged[[f"feat__{f}_b" for f in feature_names]].to_numpy(float))
        pred_equal = bool(np.allclose(pa, pb, rtol=0, atol=1e-6))
    return {"n_common_events": int(len(merged)), "features_identical": feats_equal,
           "targets_identical_before_cutoff": targets_equal, "model_predictions_identical": pred_equal,
           "pass": bool(feats_equal and targets_equal and pred_equal)}


def _r2_fn(train_mean: float):
    def _fn(y, p):
        y, p = np.asarray(y, float), np.asarray(p, float)
        ss_tot = float(np.sum((y - train_mean) ** 2))
        return 1.0 - float(np.sum((y - p) ** 2)) / ss_tot if ss_tot > 0 else 0.0
    return _fn


# ==========================================================================
# §26 gates (mirrors Phase 81's structure, adapted for a regression target)
# ==========================================================================
def evaluate_gates_82(dataset_ok: bool, leakage_ok: bool, determinism_match: bool,
                      residualization_methodology_ok: bool, event_selection_ok: bool,
                      cross_asset_complete: bool, cross_year_complete: bool,
                      real_r2: Optional[float], placebo_r2: Optional[float],
                      shuffled_r2: Optional[float], holdout_match: bool) -> Dict[str, Any]:
    gate_h = bool(real_r2 is not None and placebo_r2 is not None
                 and real_r2 > placebo_r2 + _GATE_H_R2_MARGIN)
    gate_i = bool(shuffled_r2 is not None and shuffled_r2 < _GATE_H_R2_MARGIN)
    gates = {
        "A_dataset_integrity": dataset_ok, "B_leakage": leakage_ok,
        "C_reproducibility": determinism_match,
        "D_residualization_methodology": residualization_methodology_ok,
        "E_event_selection_valid": event_selection_ok,
        "F_cross_asset_complete": cross_asset_complete, "G_cross_year_complete": cross_year_complete,
        "H_matched_placebo": gate_h, "I_shuffled_target": gate_i, "J_holdout_protected": holdout_match,
    }
    return {"gates": gates, "all_pass": all(gates.values()), "n_pass": sum(gates.values())}


def classify_verdict_82(gates: Dict[str, Any], delta_m6_minus_m5: Optional[float],
                        delta_ci_excludes_zero: bool, cross_year_signs: List[Optional[bool]],
                        cross_asset_signs: List[Optional[bool]]) -> Tuple[str, str]:
    """§50/§69 -- exactly one of four controlled outcomes, predeclared rule.
    ``delta_m6_minus_m5`` is OOS R^2(M6) - OOS R^2(M5) -- the central
    "does compression add value beyond volatility+time" comparison."""
    hard = ("A_dataset_integrity", "B_leakage", "C_reproducibility", "E_event_selection_valid",
           "J_holdout_protected")
    if not all(gates["gates"][g] for g in hard):
        return "V1_TARGET_OR_PIPELINE_INVALID", "a hard integrity/leakage/event-selection/reproducibility/holdout gate failed"
    if delta_m6_minus_m5 is None:
        return "V1_TARGET_OR_PIPELINE_INVALID", "headline delta could not be computed"
    # "material" R^2 improvement margin: reused proportionally from the AUC-scale
    # 0.05 material margin used throughout Phases 80/81 (R^2 lives on a
    # different scale; 0.01 R^2 is the documented, predeclared analogue)
    small = delta_m6_minus_m5 < _GATE_H_R2_MARGIN
    if small or not gates["gates"]["H_matched_placebo"]:
        return ("V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT",
               "compression duration adds negligible (or placebo-indistinguishable) OOS R^2 "
               "beyond volatility + time/session alone")
    signs_year = [s for s in cross_year_signs if s is not None]
    signs_asset = [s for s in cross_asset_signs if s is not None]
    year_consistent = bool(signs_year) and all(signs_year)
    asset_consistent = bool(signs_asset) and (sum(signs_asset) / len(signs_asset) >= 0.6)
    if (delta_ci_excludes_zero and year_consistent and asset_consistent
            and gates["gates"]["H_matched_placebo"] and gates["gates"]["I_shuffled_target"]):
        return ("V1_INCREMENTAL_INFORMATION_CONFIRMED",
               "compression duration's incremental information beyond volatility+time survives "
               "OOS, matched placebo, cross-year, and cross-asset checks")
    return ("V1_SIGNAL_PRESENT_BUT_UNSTABLE",
           "a positive incremental delta exists but is not consistently stable across "
           "years/assets or its CI does not exclude zero")


# ==========================================================================
# §56 result schema / experiment record
# ==========================================================================
@dataclass
class Phase82Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    target_version: str
    canonical_dataset_version: str
    extended_dataset_version: str
    feature_schema_version: str
    v1_definition: Dict[str, Any]
    universe: List[str]
    timeframe: str
    horizons: List[int]
    feature_groups: Dict[str, Any]
    dataset_summary: Dict[str, Any]
    feature_target_contract: Dict[str, Any]
    event_integrity: Dict[str, Any]
    duration_statistics: Dict[str, Any]
    duration_dose_response: Dict[str, Any]
    duration_severity_decorrelation: Dict[str, Any]
    volatility_conditional: Dict[str, Any]
    session_conditional: Dict[str, Any]
    range_conditional: Dict[str, Any]
    session_x_duration: Dict[str, Any]
    folds: Dict[str, List[Dict[str, Any]]]
    nested_models: List[Dict[str, Any]]
    extended_ablation: List[Dict[str, Any]]
    residual_analysis: Dict[str, Any]
    ml_reference_models: List[Dict[str, Any]]
    cross_asset: Dict[str, Any]
    cross_year: Dict[str, Any]
    leave_one_asset_out: Dict[str, Any]
    horizon_analysis: List[Dict[str, Any]]
    controls: Dict[str, Any]
    bootstrap: Dict[str, Any]
    error_analysis: Dict[str, Any]
    determinism: Dict[str, Any]
    gates: Dict[str, Any]
    verdict: str
    verdict_reason: str
    v1_research_decision: Dict[str, Any]
    phase83_queue: List[Dict[str, Any]]
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


def _nested_sweep_82(ds: pd.DataFrame, folds: List[Fold], tf: str
                     ) -> Tuple[List[Dict[str, Any]], Dict[Tuple[int, str], Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    fits: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for fold in folds:
        train, _val, test, _rep = split_fold(ds, fold, tf)
        if len(train) < 200 or len(test) < 30:
            continue
        for name, feats in NESTED_MODELS_82.items():
            r = fit_and_eval_82(train, test, feats, _PRIMARY_MODEL)
            rows.append({"fold": fold.fold, "model_group": name, "model": _PRIMARY_MODEL,
                        "n_features": len(feats), "n_train": r["n_train"], "n_test": len(test),
                        "metrics": r["metrics"], "coefficients": r.get("coefficients")})
            fits[(fold.fold, name)] = r
    return rows, fits


def run() -> Phase82Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()
    _clear_bar_cache_82()

    v1_definition = {
        "compression_threshold_atr_rank": _COMPRESSION_RANK_THR,
        "min_consecutive_compressed_bars": _COMPRESSION_MIN_RUN,
        "target_formula": "RAW ratio: (sum(true_range, event_idx+1..event_idx+h)) / "
                         "(atr_stable(event_idx) * h) - 1. NOT baseline-centred for the ML "
                         "target (see target_centering_correction); baseline_mean is stored "
                         "as metadata only, for continuity-checking against Phase 78/79.",
        "atr_stable_definition": "trailing-200-bar mean of ATR(14) -- NOT the event-time ATR",
        "target_centering_correction": (
            "Phase 78/79's study_range_expansion additionally subtracts this ratio's "
            "unconditional mean over the WHOLE dev/oos slice (a global, non-causal constant, "
            "valid for one-time aggregate hypothesis testing). The future-shock invariance "
            "test (§34) caught that this constant shifts every row's value when ANY future bar "
            "changes, even though every FEATURE and every MODEL PREDICTION at those rows is "
            "unaffected. Resolved by using the RAW ratio as the ML label, matching Phase 80's "
            "own precedent (V2's ML target is the raw label, not the baseline-centred effect)."),
        "horizons_bars": list(ALL_HORIZONS), "headline_horizon": PRIMARY_HORIZON,
        "timeframe": PRIMARY_TF, "target_version": TARGET_VERSION,
        "ambiguity_resolution": (
            "Phase 78's literal event builder (_b_compression_duration) selects ONLY comp_run == "
            "min_run, so duration is a CONSTANT (=3) at every literal event -- verified empirically "
            "(set(comp_run[event_idx]) == {3}). Studying duration as a variable therefore requires "
            "a DOCUMENTED, minimal generalisation: every bar with comp_run >= min_run is treated as "
            "an event (not only the first). The compression threshold, minimum run, ATR denominator, "
            "target formula, and baseline-centering are UNCHANGED between the two populations -- "
            "only which qualifying bars count as separate rows differs. The canonical (comp_run==3) "
            "population is reproduced separately as a continuity check against Phase 78/79's own "
            "published numbers; the extended (comp_run>=3) population is this phase's PRIMARY "
            "dataset."),
    }

    # ---- §2/§6 canonical continuity check -----------------------------------
    canon_ds = build_pooled_v1_dataset(PRIMARY_HORIZON, canonical=True)
    canon_check = {"n_events": int(len(canon_ds)),
                  "duration_values_present": sorted(canon_ds["feat__duration"].unique().tolist())
                  if not canon_ds.empty else [],
                  "mean_target": round(float(canon_ds["target"].mean()), 6) if not canon_ds.empty else None}

    # ---- §4/§6 primary (extended) datasets, all horizons ---------------------
    ds_by_h = {h: build_pooled_v1_dataset(h, canonical=False) for h in ALL_HORIZONS}
    contract = {f"h{h}": assert_feature_target_contract(ds_by_h[h]) for h in ALL_HORIZONS}
    leakage_contract_ok = all(v.get("pass") for v in contract.values())

    all_feature_names = sum(FEATURE_GROUPS_82.values(), [])
    zero_var = zero_variance_report(ds_by_h[PRIMARY_HORIZON], all_feature_names)

    # ---- §35/§36/§37/§38 leakage / event-selection / censoring / overlap ----
    sample_df = augment(load_bars(INSTRUMENTS_V1[0], PRIMARY_TF), PRIMARY_TF)
    event_sel_audit = event_selection_audit(sample_df, extended_event_indices)
    censor_audit = censored_event_audit(sample_df, extended_event_indices, PRIMARY_HORIZON)
    overlap_extended = event_overlap_audit(extended_event_indices(sample_df), PRIMARY_HORIZON)
    overlap_canonical = event_overlap_audit(canonical_event_indices(sample_df), PRIMARY_HORIZON)
    event_integrity = {"event_selection_audit": event_sel_audit, "censored_event_audit": censor_audit,
                      "overlap_extended_population": overlap_extended,
                      "overlap_canonical_population": overlap_canonical,
                      "canonical_continuity_check": canon_check}
    event_selection_ok = bool(event_sel_audit.get("identical"))

    dataset_summary = {
        "instruments": list(INSTRUMENTS_V1), "timeframe": PRIMARY_TF,
        "rows_by_horizon": {f"h{h}": int(len(ds_by_h[h])) for h in ALL_HORIZONS},
        "target_mean_by_horizon": {f"h{h}": round(float(ds_by_h[h]["target"].mean()), 5)
                                  for h in ALL_HORIZONS},
        "canonical_n_events_headline": canon_check["n_events"],
    }
    dataset_ok = (set(INSTRUMENTS_V1) == set(ds_by_h[PRIMARY_HORIZON]["instrument"].unique())
                 and all(len(ds_by_h[h]) > 1000 for h in ALL_HORIZONS)
                 and not any(zero_var.values()))

    # ---- §13/§14/§15/§16/§17/§18 descriptive analyses (full headline dataset)
    ds_h4 = ds_by_h[PRIMARY_HORIZON]
    duration_stats = compute_duration_statistics(ds_h4)
    dose_response = compute_duration_dose_response(ds_h4)
    decorrelation = duration_severity_decorrelation(ds_h4)
    vol_tercile = volatility_tercile(ds_h4)
    sess = session_label(ds_h4)
    volatility_conditional = {
        "duration_by_volatility_tercile": duration_by_condition(ds_h4, vol_tercile),
        "target_by_volatility_tercile": conditional_dose_response(ds_h4, vol_tercile),
    }
    session_conditional = {
        "duration_by_session": duration_by_condition(ds_h4, sess),
        "target_by_session": conditional_dose_response(ds_h4, sess),
        "target_by_hour": conditional_dose_response(ds_h4, ds_h4["feat__hour_sin"].round(2)),
    }
    range_tercile = pd.cut(ds_h4["feat__tr_atr"].to_numpy(float), bins=3, labels=("low", "mid", "high"))
    range_conditional = {"target_by_recent_range_tercile": conditional_dose_response(ds_h4, range_tercile)}
    dur_bucket = _duration_bucket(ds_h4["feat__duration"].to_numpy(float))
    session_x_duration = conditional_dose_response(
        ds_h4.assign(_key=[f"{d}|{s}" for d, s in zip(dur_bucket, sess)]),
        ds_h4.assign(_key=[f"{d}|{s}" for d, s in zip(dur_bucket, sess)])["_key"])

    # ---- §24 folds (calendar-year, reused unchanged) -------------------------
    folds = make_folds(ds_h4, _FOLD_BOUNDARY_YEARS)
    folds_dict = {"15m": [f.to_dict() for f in folds]}
    test_period_label = {1: "2023_H2", 2: "2024_H2", 3: "2025_H2_onward"}

    # ---- §10/§39 nested model sweep (headline, Ridge primary) ---------------
    nested_rows, nested_fits = _nested_sweep_82(ds_h4, folds, PRIMARY_TF)
    for row in nested_rows:
        row["test_period"] = test_period_label[row["fold"]]

    headline_fold = folds[-1]
    headline_train, _hv, headline_test, headline_split_report = split_fold(ds_h4, headline_fold, PRIMARY_TF)

    # ---- §43 extended ablation (only letters without an M-equivalent are new)
    extended_rows: List[Dict[str, Any]] = []
    for fold in folds:
        train, _v, test, _r = split_fold(ds_h4, fold, PRIMARY_TF)
        if len(train) < 200 or len(test) < 30:
            continue
        for name, feats in ABLATION_82.items():
            r = fit_and_eval_82(train, test, feats, _PRIMARY_MODEL)
            extended_rows.append({"fold": fold.fold, "test_period": test_period_label[fold.fold],
                                  "ablation": name, "metrics": r["metrics"]})

    # ---- §19 ML reference models (RF, HGB) at the 3 key comparisons ----------
    ml_ref_rows: List[Dict[str, Any]] = []
    for fold in folds:
        train, _v, test, _r = split_fold(ds_h4, fold, PRIMARY_TF)
        if len(train) < 200 or len(test) < 30:
            continue
        for name in ("M5_volatility_time", "M6_compression_volatility_time", "M8_full"):
            for m in _REFERENCE_MODELS:
                r = fit_and_eval_82(train, test, NESTED_MODELS_82[name], m)
                ml_ref_rows.append({"fold": fold.fold, "test_period": test_period_label[fold.fold],
                                   "model_group": name, "model": m, "metrics": r["metrics"]})

    # ---- §40/§41 residualization (headline fold, train-only) -----------------
    context_ds_features = FEATURE_GROUPS_82["VOLATILITY"] + FEATURE_GROUPS_82["TIME"]
    resid1 = compute_context_residual(headline_train, headline_test, context_ds_features)
    comp_feats = headline_test[[f"feat__{f}" for f in FEATURE_GROUPS_82["COMPRESSION"]]]
    resid1_info = evaluate_residual_information(resid1["residual"], comp_feats)

    context2_features = context_ds_features + FEATURE_GROUPS_82["RANGE_PRICE"]
    resid2 = compute_context_residual(headline_train, headline_test, context2_features)
    resid2_info = evaluate_residual_information(resid2["residual"], comp_feats)
    residualization_methodology_ok = (resid1_info.get("state") != "INSUFFICIENT_SAMPLE"
                                      and resid2_info.get("state") != "INSUFFICIENT_SAMPLE")
    residual_analysis = {
        "vs_volatility_time": {"residual_summary": {k: v for k, v in resid1.items() if k != "residual"},
                              "compression_explains_residual": resid1_info},
        "vs_volatility_time_range": {"residual_summary": {k: v for k, v in resid2.items() if k != "residual"},
                                    "compression_explains_residual": resid2_info},
    }

    # ---- §27/§28 cross-asset + leave-one-out (headline fold) -----------------
    def _per_instrument(fit: Dict[str, Any]) -> Dict[str, Any]:
        p_pred, y_true = fit["_p_pred"], fit["_y_true"]
        train_mean = fit["train_mean"]
        out = {}
        test_reset = headline_test.reset_index(drop=True)
        for inst in sorted(test_reset["instrument"].unique()):
            m = (test_reset["instrument"] == inst).to_numpy()
            if m.sum() < 100:
                out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
                continue
            out[inst] = compute_regression_metrics(y_true[m], p_pred[m], train_mean)
        return out

    fit_m5 = nested_fits[(headline_fold.fold, "M5_volatility_time")]
    fit_m6 = nested_fits[(headline_fold.fold, "M6_compression_volatility_time")]
    cross_asset_m5 = _per_instrument(fit_m5)
    cross_asset_m6 = _per_instrument(fit_m6)
    cross_asset_delta = {}
    for inst in INSTRUMENTS_V1:
        r5 = cross_asset_m5.get(inst, {}).get("oos_r2")
        r6 = cross_asset_m6.get(inst, {}).get("oos_r2")
        cross_asset_delta[inst] = round(r6 - r5, 5) if (r5 is not None and r6 is not None) else None
    cross_asset = {"m5_volatility_time": cross_asset_m5, "m6_compression_volatility_time": cross_asset_m6,
                  "delta_m6_minus_m5": cross_asset_delta, "n_instruments_evaluated": len(cross_asset_delta)}
    cross_asset_complete = len(cross_asset_delta) == len(INSTRUMENTS_V1)

    loo_rows: Dict[str, Any] = {}
    for held_out in INSTRUMENTS_V1:
        train_wo = headline_train[headline_train["instrument"] != held_out]
        test_held = headline_test[headline_test["instrument"] == held_out]
        if len(train_wo) < 500 or len(test_held) < 100:
            loo_rows[held_out] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        r5 = fit_and_eval_82(train_wo, test_held, NESTED_MODELS_82["M5_volatility_time"], _PRIMARY_MODEL)
        r6 = fit_and_eval_82(train_wo, test_held, NESTED_MODELS_82["M6_compression_volatility_time"],
                            _PRIMARY_MODEL)
        loo_rows[held_out] = {"m5_r2": r5["metrics"]["oos_r2"], "m6_r2": r6["metrics"]["oos_r2"],
                              "delta": round(r6["metrics"]["oos_r2"] - r5["metrics"]["oos_r2"], 5)}
    leave_one_out = {"per_instrument_held_out": loo_rows}

    # ---- §30 horizon analysis (M5 & M6, all folds, all horizons) -------------
    horizon_rows: List[Dict[str, Any]] = []
    for h in ALL_HORIZONS:
        ds_hh = ds_by_h[h]
        folds_h = folds if h == PRIMARY_HORIZON else make_folds(ds_hh, _FOLD_BOUNDARY_YEARS)
        for fold in folds_h:
            if h == PRIMARY_HORIZON:
                for name in ("M5_volatility_time", "M6_compression_volatility_time"):
                    fit = nested_fits.get((fold.fold, name))
                    if fit:
                        horizon_rows.append({"horizon": h, "fold": fold.fold,
                                            "test_period": test_period_label[fold.fold],
                                            "model_group": name, "metrics": fit["metrics"]})
                continue
            train, _v, test, _r = split_fold(ds_hh, fold, PRIMARY_TF)
            if len(train) < 200 or len(test) < 30:
                continue
            for name in ("M5_volatility_time", "M6_compression_volatility_time"):
                r = fit_and_eval_82(train, test, NESTED_MODELS_82[name], _PRIMARY_MODEL)
                horizon_rows.append({"horizon": h, "fold": fold.fold,
                                    "test_period": test_period_label[fold.fold],
                                    "model_group": name, "metrics": r["metrics"]})
        del ds_hh
    gc.collect()

    # ---- §31/§32/§33/§34 controls (headline fold) ----------------------------
    shuffled = shuffled_target_control(headline_train, headline_test,
                                       NESTED_MODELS_82["M6_compression_volatility_time"], _PRIMARY_MODEL)
    placebo_m5 = matched_placebo_control(headline_train, headline_test,
                                        NESTED_MODELS_82["M5_volatility_time"], _PRIMARY_MODEL,
                                        PRIMARY_HORIZON)
    placebo_m6 = matched_placebo_control(headline_train, headline_test,
                                        NESTED_MODELS_82["M6_compression_volatility_time"], _PRIMARY_MODEL,
                                        PRIMARY_HORIZON)
    shift_sweep_m6 = temporal_shift_sweep(headline_train, headline_test,
                                         NESTED_MODELS_82["M6_compression_volatility_time"],
                                         _PRIMARY_MODEL, PRIMARY_HORIZON)
    future_shock = check_future_shock_invariance()
    controls = {
        "shuffled_target": shuffled,
        "matched_placebo": {"m5_volatility_time": placebo_m5,
                           "m6_compression_volatility_time": placebo_m6,
                           "shift_bars": _MATCHED_PLACEBO_SHIFT_BARS},
        "temporal_shift_sweep": {"m6_compression_volatility_time": shift_sweep_m6},
        "future_shock_invariance": future_shock,
    }

    # ---- §26 bootstrap: headline delta(M6 - M5), R^2 metric ------------------
    train_mean_h = fit_m5["train_mean"]
    delta_boot = bootstrap_delta_ci(fit_m5["_y_true"], fit_m6["_p_pred"], fit_m5["_p_pred"],
                                    _r2_fn(train_mean_h), block=PRIMARY_HORIZON)
    bootstrap = {"delta_r2_m6_minus_m5": delta_boot}

    error_analysis = {"m6_error_deciles": fit_m6.get("error_deciles")}

    # ---- §62 in-process determinism recheck (headline nested sweep) ---------
    def _headline_signature() -> str:
        parts = [{"group": name, "metrics": nested_fits[(headline_fold.fold, name)]["metrics"]}
                for name in NESTED_MODELS_82 if (headline_fold.fold, name) in nested_fits]
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()

    sig_a = _headline_signature()
    _, rerun_fits = _nested_sweep_82(ds_h4, [headline_fold], PRIMARY_TF)
    parts_b = [{"group": name, "metrics": rerun_fits[(headline_fold.fold, name)]["metrics"]}
              for name in NESTED_MODELS_82 if (headline_fold.fold, name) in rerun_fits]
    sig_b = hashlib.sha256(json.dumps(parts_b, sort_keys=True, default=str).encode()).hexdigest()
    determinism = {"headline_signature_a": sig_a, "headline_signature_b": sig_b, "match": sig_a == sig_b}

    # ---- §26 gates + verdict --------------------------------------------------
    leakage_ok = leakage_contract_ok and future_shock.get("pass", False)
    real_r2_m6 = fit_m6["metrics"].get("oos_r2")
    placebo_r2_m6 = (placebo_m6 or {}).get("metrics", {}).get("oos_r2")
    shuffled_r2 = shuffled.get("metrics", {}).get("oos_r2")
    gates = evaluate_gates_82(dataset_ok, leakage_ok, determinism["match"],
                              residualization_methodology_ok, event_selection_ok,
                              cross_asset_complete, True, real_r2_m6, placebo_r2_m6, shuffled_r2, True)

    delta_m6_minus_m5 = delta_boot.get("point") if delta_boot.get("state") != "INSUFFICIENT_SAMPLE" else None
    delta_ci_excludes_zero = bool(delta_boot.get("excludes_zero"))
    cross_year_signs = []
    for fold in folds:
        r5 = nested_fits.get((fold.fold, "M5_volatility_time"), {}).get("metrics", {}).get("oos_r2")
        r6 = nested_fits.get((fold.fold, "M6_compression_volatility_time"), {}).get("metrics", {}).get("oos_r2")
        cross_year_signs.append(bool(r6 > r5) if (r5 is not None and r6 is not None) else None)
    cross_asset_signs = [bool(v > 0) if v is not None else None for v in cross_asset_delta.values()]

    verdict, verdict_reason = classify_verdict_82(gates, delta_m6_minus_m5, delta_ci_excludes_zero,
                                                  cross_year_signs, cross_asset_signs)

    v1_research_decision = {
        "question": "Does compression duration provide incremental predictive information about "
                   "subsequent range expansion, beyond volatility and time/session structure?",
        "answer": "YES" if verdict == "V1_INCREMENTAL_INFORMATION_CONFIRMED" else "NO",
        "reasoning": verdict_reason,
        "further_research_justified": verdict in ("V1_INCREMENTAL_INFORMATION_CONFIRMED",
                                                   "V1_SIGNAL_PRESENT_BUT_UNSTABLE"),
    }
    phase83_queue: List[Dict[str, Any]] = []
    if verdict == "V1_INCREMENTAL_INFORMATION_CONFIRMED":
        phase83_queue.append({"item": "Narrowly scoped follow-up validating the specific residual "
                              "compression-duration effect identified here", "scope": "no trading integration"})
    elif verdict == "V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT":
        phase83_queue.append({"item": "Treat V1 as a documented, context-explained descriptive "
                              "phenomenon; no further ML development for V1",
                              "scope": "research closed for V1's predictive-modelling line"})
    elif verdict == "V1_SIGNAL_PRESENT_BUT_UNSTABLE":
        phase83_queue.append({"item": "Record V1 residual-information instability as a negative "
                              "result; do not re-tune this pipeline against these results",
                              "scope": "research closed pending independently new evidence"})
    else:
        phase83_queue.append({"item": "Diagnose and fix the identified pipeline/leakage/"
                              "reproducibility issue before any further interpretation",
                              "scope": "blocking"})
    phase83_queue = phase83_queue[:3]

    ident = json.dumps({
        "schema": SCHEMA_VERSION, "verdict": verdict, "gates": gates["gates"],
        "delta_m6_minus_m5": delta_m6_minus_m5,
        "nested_rows": sorted((r["fold"], r["model_group"], r["metrics"].get("oos_r2"))
                             for r in nested_rows),
    }, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase82Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        target_version=TARGET_VERSION, canonical_dataset_version=CANONICAL_DATASET_VERSION,
        extended_dataset_version=EXTENDED_DATASET_VERSION, feature_schema_version=FEATURE_SCHEMA_VERSION,
        v1_definition=v1_definition, universe=list(INSTRUMENTS_V1), timeframe=PRIMARY_TF,
        horizons=list(ALL_HORIZONS), feature_groups=feature_group_registry_dicts(),
        dataset_summary=dataset_summary, feature_target_contract=contract, event_integrity=event_integrity,
        duration_statistics=duration_stats, duration_dose_response=dose_response,
        duration_severity_decorrelation=decorrelation, volatility_conditional=volatility_conditional,
        session_conditional=session_conditional, range_conditional=range_conditional,
        session_x_duration=session_x_duration, folds=folds_dict, nested_models=nested_rows,
        extended_ablation=extended_rows, residual_analysis=residual_analysis,
        ml_reference_models=ml_ref_rows, cross_asset=cross_asset, cross_year={
            "per_fold": [{"fold": f.fold, "test_period": test_period_label[f.fold],
                        "m5_r2": nested_fits.get((f.fold, "M5_volatility_time"), {}).get(
                            "metrics", {}).get("oos_r2"),
                        "m6_r2": nested_fits.get((f.fold, "M6_compression_volatility_time"), {}).get(
                            "metrics", {}).get("oos_r2")} for f in folds]},
        leave_one_asset_out=leave_one_out, horizon_analysis=horizon_rows, controls=controls,
        bootstrap=bootstrap, error_analysis=error_analysis, determinism=determinism, gates=gates,
        verdict=verdict, verdict_reason=verdict_reason, v1_research_decision=v1_research_decision,
        phase83_queue=phase83_queue, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase82Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase82_compression_expansion_ml_pilot", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 82 - V1 15m compression -> expansion ML pilot ...", flush=True)
    res = run()
    print(f"\n=== PHASE 82 ({res.runtime_seconds}s) ===")
    print(f"Dataset: {json.dumps(res.dataset_summary, default=str)}")
    print("\nNested models (headline fold 3):")
    for r in res.nested_models:
        if r["fold"] == 3:
            print(f"  {r['model_group']:<32} n_feat={r['n_features']:<3} R2={r['metrics']['oos_r2']} "
                 f"MAE={r['metrics']['mae']}")
    print(f"\nBootstrap delta R2(M6-M5): {json.dumps(res.bootstrap, default=str)}")
    print(f"\nGates: {json.dumps(res.gates, default=str)}")
    print(f"\nDeterminism match: {res.determinism['match']}")
    print(f"\nVERDICT: {res.verdict}  ({res.verdict_reason})")
    print(f"\nV1 RESEARCH DECISION: {res.v1_research_decision['answer']}")
    print(f"\nPHASE 83 QUEUE ({len(res.phase83_queue)}):")
    for q in res.phase83_queue:
        print(f"  {q}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "FEATURE_GROUPS_82", "NESTED_MODELS_82", "ABLATION_82", "feature_group_registry_dicts",
    "canonical_event_indices", "extended_event_indices", "build_canonical_v1_dataset",
    "build_v1_dataset", "build_pooled_v1_dataset", "assert_feature_target_contract",
    "event_selection_audit", "censored_event_audit", "event_overlap_audit",
    "compute_regression_metrics", "error_by_prediction_decile", "fit_and_eval_82",
    "zero_variance_report", "compute_duration_statistics", "compute_duration_dose_response",
    "conditional_dose_response", "duration_by_condition", "volatility_tercile", "session_label",
    "duration_severity_decorrelation", "compute_context_residual", "evaluate_residual_information",
    "ARTIFACT_KEY", "SCHEMA_VERSION", "TARGET_VERSION", "CANONICAL_DATASET_VERSION",
    "EXTENDED_DATASET_VERSION", "FEATURE_SCHEMA_VERSION", "PRIMARY_TF", "PRIMARY_HORIZON",
    "ALL_HORIZONS", "INSTRUMENTS_V1", "shuffled_target_control", "matched_placebo_targets",
    "matched_placebo_control", "temporal_shift_sweep", "check_future_shock_invariance",
    "evaluate_gates_82", "classify_verdict_82", "run", "persist", "get_result", "main",
    "Phase82Result",
]
