# -*- coding: utf-8 -*-
"""
Phase 80 — ML Volatility Regime Prediction Pilot.

The first phase in which a predictive ML model is permitted. Still a
research-only pilot: the objective is NOT a profitable trading strategy, it
is whether machine learning can predict the Phase 78/79 V2 volatility-regime
target strictly out-of-sample, and whether it adds information BEYOND trivial
persistence/baseline predictors (§2 of the master prompt). No trading signal
is produced. No execution/broker/risk module is imported.

Reuses the Phase 76/78/79 machinery UNCHANGED wherever it applies: causal bar
loading (`phase76_event_study.load_bars`), causal feature augmentation
(`phase78_market_behavior_discovery_ii.augment`), and — critically — the
EXACT V2 event definition (`_b_vol_bucket_high`) and target formula
(`rv_rank[i+h] > 0.66`) that Phase 78 discovered and Phase 79 certified
`TARGET_INTEGRITY_READY`. Nothing about the target is redefined here.

Architecture note (§0/§50): a generic, reusable ML research framework —
FeatureSpec/registry, dataset builder, purged calendar-quantile walk-forward
splitter, baseline predictors, model trainer/evaluator, ablation runner,
permutation importance, shuffled-target/placebo/future-shock controls,
experiment record — is built once in this module and instantiated for V2.
Phase 76-79's `backtester.run_walk_forward` (used by `tests/test_wfo.py`) was
inspected and NOT reused: it optimizes a strategy's SL/TP grid against
simulated trade PnL, a different domain (trade simulation, not a labelled
tabular classification dataset) — reusing it would force this pilot's
evaluation vocabulary into a strategy-backtesting shape it doesn't have.

No deep learning. Models are `sklearn` (already a project dependency via
`ml_trainer.py` / `requirements.txt`: `scikit-learn>=1.3.0`) —
`LogisticRegression`, `RandomForestClassifier`,
`HistGradientBoostingClassifier` (sklearn's built-in gradient boosting — no
new dependency for "gradient boosting model available in the existing
environment", §11).

Read-only research. The frozen Phase-74 holdout is never read (§43).
"""
from __future__ import annotations

import gc
import hashlib
import inspect as _inspect
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest import mock

import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score,
                              balanced_accuracy_score, brier_score_loss,
                              confusion_matrix, f1_score, log_loss,
                              precision_score, recall_score, roc_auc_score)
from sklearn.inspection import permutation_importance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
import phase79_ml_target_integrity as p79
from phase76_event_study import FWD_HORIZONS, load_bars
from phase78_market_behavior_discovery_ii import INSTRUMENTS, _b_vol_bucket_high, augment

SCHEMA_VERSION = "phase80.1"
ARTIFACT_KEY = "phase80_ml_volatility_regime"
RANDOM_SEED = 42

TARGET_VERSION = p79.V2_TARGET_SPEC.version          # "V2-target-v1" -- unchanged, imported not redefined
FEATURE_SCHEMA_VERSION = "phase80-features-v1"
DATASET_VERSION = "phase80-dataset-v1"

_TF_SECONDS: Dict[str, int] = {"15m": 900, "1h": 3600}
PRIMARY_TF = "15m"
SECONDARY_TF = "1h"
PRIMARY_HORIZON = 4                                    # matches phase76._headline_h("15m")
ALL_HORIZONS: Tuple[int, ...] = FWD_HORIZONS           # (1, 2, 4, 8) -- unchanged
INSTRUMENTS_V2: Tuple[str, ...] = INSTRUMENTS          # unchanged 6-instrument universe
_WARMUP = 200

_N_FOLDS_PRIMARY = 3
_N_FOLDS_SECONDARY = 2
# Calendar-YEAR fold boundaries (not data quantiles): each fold's TEST window
# is a distinct calendar half-year/year, so the walk-forward IS the cross-year
# analysis (§16 walk-forward + §19 cross-year are the same experiment here,
# not two separate ones) -- train<year_start, val=H1 of that year, test=H2
# onward (until the next boundary). A quantile-based scheme was tried first
# and rejected: because every fold's TEST window necessarily sits in the tail
# of the data (that is what "walk-forward" means), a small number of
# quantile folds would ALL land in 2025-2026, structurally unable to report
# genuine OOS performance for 2023/2024 at all -- an honest limitation
# documented rather than silently worked around.
_FOLD_BOUNDARY_YEARS: Tuple[int, ...] = (2023, 2024, 2025)
_FOLD_BOUNDARY_YEARS_SECONDARY: Tuple[int, ...] = (2024, 2025)   # 1h: fewer folds, more history per fold
_EMBARGO_BARS = max(ALL_HORIZONS)                      # 8 bars, translated to seconds per TF
_TRAIN_CAP_ROWS = 50_000                                # computational bound, documented (§ engineering note)

_SHUFFLE_SEED = 80001
_PLACEBO_SEED = 80002


# ==========================================================================
# §7 Feature registry (§6 conservative feature set, §8 groups)
# ==========================================================================
@dataclass(frozen=True)
class FeatureSpec:
    name: str
    group: str
    description: str
    lookback_bars: Optional[int]
    uses_current_bar: bool
    future_safe: bool
    formula: str
    version: str

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


FEATURE_REGISTRY: List[FeatureSpec] = [
    FeatureSpec("ret_1", "PRICE", "last 1-bar log return", 1, True, True,
               "ret[i]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("ret_4", "PRICE", "trailing 4-bar log return", 4, True, True,
               "log(close[i]/close[i-4])", FEATURE_SCHEMA_VERSION),
    FeatureSpec("ret_8", "PRICE", "trailing 8-bar log return", 8, True, True,
               "log(close[i]/close[i-8])", FEATURE_SCHEMA_VERSION),
    FeatureSpec("abs_ret_1", "PRICE", "absolute 1-bar log return", 1, True, True,
               "abs(ret[i])", FEATURE_SCHEMA_VERSION),
    FeatureSpec("ret_sign_1", "PRICE", "sign of the 1-bar log return", 1, True, True,
               "sign(ret[i])", FEATURE_SCHEMA_VERSION),
    FeatureSpec("atr_ret", "VOLATILITY", "ATR(14) / price (Phase76 atr_ret, unchanged)",
               14, True, True, "atr_ret[i]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("atr_rank", "VOLATILITY", "trailing 200-bar ATR percentile rank (Phase76, unchanged)",
               200, True, True, "atr_rank[i]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("rv", "VOLATILITY", "trailing 4-bar realized volatility (Phase78 rv, unchanged)",
               4, True, True, "rv[i]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("rv_rank", "VOLATILITY",
               "trailing 200-bar realized-vol percentile rank -- the CURRENT-STATE feature. "
               "By construction every V2 event row has rv_rank > 0.66 (that IS the event "
               "definition), so this feature has restricted but real variance (0.66-1.0), "
               "encoding 'how extremely HIGH' the current bar is, not merely THAT it is HIGH.",
               200, True, True, "rv_rank[i]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("rv_change_1", "VOLATILITY", "1-bar change in rv", 5, True, True,
               "rv[i]-rv[i-1]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("atr_rank_change_1", "VOLATILITY", "1-bar change in atr_rank", 201, True, True,
               "atr_rank[i]-atr_rank[i-1]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("regime_high_duration", "REGIME",
               "consecutive bars (ending at i, inclusive) with rv_rank > 0.66 -- the "
               "CURRENT-STATE duration feature: how long the HIGH regime has already run. "
               "Always >= 1 for a V2 event row by construction.",
               None, True, True, "run_length(rv_rank>0.66)[i]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("regime_code", "REGIME", "Phase76 causal regime (TRENDING=2/MIXED=1/RANGING=0)",
               20, True, True, "code(regime[i])", FEATURE_SCHEMA_VERSION),
    FeatureSpec("body_range_ratio", "CANDLE", "|close-open| / max(high-low, eps)", 1, True, True,
               "body/range", FEATURE_SCHEMA_VERSION),
    FeatureSpec("upper_wick_ratio", "CANDLE", "(high-max(open,close)) / max(high-low, eps)",
               1, True, True, "upper_wick/range", FEATURE_SCHEMA_VERSION),
    FeatureSpec("lower_wick_ratio", "CANDLE", "(min(open,close)-low) / max(high-low, eps)",
               1, True, True, "lower_wick/range", FEATURE_SCHEMA_VERSION),
    FeatureSpec("tr_atr", "CANDLE", "true range / ATR(14) (Phase76 tr_atr, unchanged)",
               14, True, True, "tr_atr[i]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("hour", "TIME", "UTC hour-of-day", 1, True, True, "hour[i]", FEATURE_SCHEMA_VERSION),
    FeatureSpec("dow", "TIME", "UTC day-of-week (0=Mon)", 1, True, True,
               "date[i].weekday()", FEATURE_SCHEMA_VERSION),
    FeatureSpec("session_code", "TIME", "Phase76 session bucket, integer-coded", 1, True, True,
               "code(session[i])", FEATURE_SCHEMA_VERSION),
]
FEATURE_NAMES = [f.name for f in FEATURE_REGISTRY]
FEATURE_GROUPS: Dict[str, List[str]] = {}
for _f in FEATURE_REGISTRY:
    FEATURE_GROUPS.setdefault(_f.group, []).append(_f.name)

# §24 ablation sets — deliberately explicit, no silent "give the model everything"
ABLATION_SETS: Dict[str, List[str]] = {
    "A_current_state_only": ["rv_rank", "regime_high_duration"],
    "B_plus_volatility": ["rv_rank", "regime_high_duration", "atr_ret", "atr_rank",
                          "rv", "rv_change_1", "atr_rank_change_1"],
    "C_plus_price": ["rv_rank", "regime_high_duration", "atr_ret", "atr_rank", "rv",
                     "rv_change_1", "atr_rank_change_1", "ret_1", "ret_4", "ret_8",
                     "abs_ret_1", "ret_sign_1"],
    "D_full_conservative": FEATURE_NAMES,
}


def feature_registry_dicts() -> List[Dict[str, Any]]:
    return [f.to_dict() for f in FEATURE_REGISTRY]


# ==========================================================================
# §5/§6 Dataset builder — every row auditable: instrument, timeframe,
# prediction_timestamp, target window, horizon, dataset/target/feature
# versions, plus every `feat__*` column.
# ==========================================================================
_REGIME_CODE = {"TRENDING": 2.0, "MIXED": 1.0, "RANGING": 0.0}
_SESSION_CODE = {"TOKYO": 0.0, "LONDON": 1.0, "LONDON_NY_OVERLAP": 2.0,
                "NEW_YORK": 3.0, "LATE_US": 4.0}


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorised, purely causal (every value at row i uses only df[..i]).
    Matches FEATURE_REGISTRY exactly, one column per entry."""
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

    rv = df["rv"].to_numpy(float)
    rv_rank = df["rv_rank"].to_numpy(float)
    atr_ret = df["atr_ret"].to_numpy(float)
    atr_rank = df["atr_rank"].to_numpy(float)

    hi_flag = np.isfinite(rv_rank) & (rv_rank > 0.66)
    regime_high_duration = p78._run_length(hi_flag).astype(float)

    rng = h - lo
    rng_safe = np.where(rng > 1e-12, rng, np.nan)
    body_range_ratio = np.abs(c - o) / rng_safe
    upper_wick_ratio = (h - np.maximum(o, c)) / rng_safe
    lower_wick_ratio = (np.minimum(o, c) - lo) / rng_safe

    regime_code = np.array([_REGIME_CODE.get(r, 1.0) for r in df["regime"].to_numpy()], float)
    session_code = np.array([_SESSION_CODE.get(s, 4.0) for s in df["session"].to_numpy()], float)
    dow = np.array([d.weekday() for d in df["date"].to_numpy()], float)

    rv_prev = np.concatenate([[np.nan], rv[:-1]])
    atr_rank_prev = np.concatenate([[np.nan], atr_rank[:-1]])

    return pd.DataFrame({
        "ret_1": ret, "ret_4": _lag_ret(4), "ret_8": _lag_ret(8),
        "abs_ret_1": np.abs(ret), "ret_sign_1": np.sign(ret),
        "atr_ret": atr_ret, "atr_rank": atr_rank, "rv": rv, "rv_rank": rv_rank,
        "rv_change_1": rv - rv_prev, "atr_rank_change_1": atr_rank - atr_rank_prev,
        "regime_high_duration": regime_high_duration, "regime_code": regime_code,
        "body_range_ratio": body_range_ratio, "upper_wick_ratio": upper_wick_ratio,
        "lower_wick_ratio": lower_wick_ratio, "tr_atr": df["tr_atr"].to_numpy(float),
        "hour": df["hour"].to_numpy(float), "dow": dow, "session_code": session_code,
    })


def build_dataset(instrument: str, tf: str, horizon: int,
                  event_idx_override: Optional[np.ndarray] = None) -> pd.DataFrame:
    """One auditable row per (instrument, timeframe, horizon, event). The
    event definition and target formula are the EXACT, unchanged Phase 78/79
    V2 definition: event = ``_b_vol_bucket_high`` (rv_rank > 0.66); target =
    ``rv_rank[event_idx + horizon] > 0.66``. ``event_idx_override`` is used
    only by the placebo control (§27) to substitute a condition-decoupled
    random event set while reusing every other line of this function."""
    df = load_bars(instrument, tf)
    if df.empty or len(df) < 2000:
        return pd.DataFrame()
    df = augment(df, tf)
    feats_all = _build_features(df)
    n = len(df)
    tf_sec = _TF_SECONDS[tf]
    open_ts = df["t"].to_numpy(np.int64)
    rv_rank = df["rv_rank"].to_numpy(float)

    idx = _b_vol_bucket_high(df)[0] if event_idx_override is None else np.asarray(event_idx_override, int)
    idx = idx[idx >= _WARMUP]
    j = idx + horizon
    valid = j < n
    idx, jv = idx[valid], j[valid]
    ok_target = np.isfinite(rv_rank[jv])
    idx, jv = idx[ok_target], jv[ok_target]
    target = (rv_rank[jv] > 0.66).astype(int)

    feat_rows = feats_all.iloc[idx].reset_index(drop=True)
    finite_mask = np.isfinite(feat_rows.to_numpy(float)).all(axis=1)
    idx, jv, target = idx[finite_mask], jv[finite_mask], target[finite_mask]
    feat_rows = feat_rows.loc[finite_mask].reset_index(drop=True)
    if len(idx) == 0:
        return pd.DataFrame()

    pred_ts = pd.to_datetime(open_ts[idx].astype(np.int64) + tf_sec, unit="s", utc=True)
    targ_end_ts = pd.to_datetime(open_ts[jv].astype(np.int64) + tf_sec, unit="s", utc=True)

    out = pd.DataFrame({
        "instrument": instrument, "timeframe": tf, "horizon_bars": horizon,
        "event_idx": idx, "target_idx": jv,
        "prediction_timestamp": pred_ts, "target_end_timestamp": targ_end_ts,
        "target": target, "dataset_version": DATASET_VERSION,
        "target_version": TARGET_VERSION, "feature_schema_version": FEATURE_SCHEMA_VERSION,
    })
    return pd.concat([out, feat_rows.add_prefix("feat__")], axis=1)


_INSTRUMENT_CODE = {inst: float(k) for k, inst in enumerate(INSTRUMENTS_V2)}


def build_pooled_dataset(tf: str, horizon: int,
                         instruments: Tuple[str, ...] = INSTRUMENTS_V2) -> pd.DataFrame:
    frames = []
    for inst in instruments:
        d = build_dataset(inst, tf, horizon)
        if not d.empty:
            frames.append(d)
    if not frames:
        return pd.DataFrame()
    pooled = pd.concat(frames, ignore_index=True)
    pooled["feat__instrument_code"] = pooled["instrument"].map(_INSTRUMENT_CODE)
    pooled = pooled.sort_values("prediction_timestamp").reset_index(drop=True)
    return pooled


# ==========================================================================
# §4 Machine-checkable prediction-timestamp contract
# ==========================================================================
def assert_feature_target_contract(dataset: pd.DataFrame) -> Dict[str, Any]:
    """Every row: target_end_timestamp is STRICTLY after prediction_timestamp,
    by at least horizon_bars * timeframe_seconds (>= , not ==, per the Phase 79
    §19 fix -- real calendar gaps only ever ADD wall-clock time)."""
    if dataset.empty:
        return {"state": "NO_ROWS"}
    tf_sec = dataset["timeframe"].map(_TF_SECONDS)
    gap = (dataset["target_end_timestamp"] - dataset["prediction_timestamp"]).dt.total_seconds()
    min_expected = dataset["horizon_bars"] * tf_sec
    ok_after = bool((dataset["target_end_timestamp"] > dataset["prediction_timestamp"]).all())
    ok_min_gap = bool((gap.to_numpy() >= min_expected.to_numpy() - 1e-6).all())
    return {"n_rows": int(len(dataset)), "target_strictly_after_prediction": ok_after,
           "gap_at_least_horizon_times_tf_seconds": ok_min_gap,
           "pass": bool(ok_after and ok_min_gap)}


# ==========================================================================
# §13/§14/§16 purged calendar-quantile walk-forward folds
# ==========================================================================
@dataclass
class Fold:
    fold: int
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {k: (v.isoformat() if isinstance(v, pd.Timestamp) else v)
               for k, v in self.__dict__.items()}


def make_folds(dataset: pd.DataFrame, boundary_years: Tuple[int, ...] = _FOLD_BOUNDARY_YEARS
              ) -> List[Fold]:
    """Expanding-window, calendar-YEAR folds computed on the POOLED dataset's
    ``prediction_timestamp`` -- a common currency across instruments, unlike
    bar index (§13: never a random split). Fold i: train = everything before
    Jan 1 of ``boundary_years[i]``; validation = H1 of that year; test = H2 of
    that year through (exclusive) the next boundary year -- so each fold's
    test window IS a distinct calendar period (§16 walk-forward and §19
    cross-year are the same experiment here). The final fold's test window
    extends to the last available bar rather than stopping at a fixed date."""
    last_ts = dataset["prediction_timestamp"].max() + pd.Timedelta(days=1)
    folds = []
    for i, y in enumerate(boundary_years):
        train_end = pd.Timestamp(f"{y}-01-01", tz="UTC")
        val_end = pd.Timestamp(f"{y}-07-01", tz="UTC")
        test_end = (pd.Timestamp(f"{boundary_years[i + 1]}-01-01", tz="UTC")
                    if i + 1 < len(boundary_years) else last_ts)
        folds.append(Fold(fold=i + 1, train_end=train_end, val_start=train_end,
                          val_end=val_end, test_start=val_end, test_end=test_end))
    return folds


def split_fold(dataset: pd.DataFrame, fold: Fold, tf: str,
              embargo_bars: int = _EMBARGO_BARS) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """§14 purge + light embargo. Purge: drop TRAIN/VAL rows whose target
    window reads AT OR PAST the boundary that separates them from the next
    split (their label would otherwise depend on information the next split
    is supposed to own). Embargo: additionally drop the first
    ``embargo_bars`` worth of VAL/TEST rows immediately after a boundary, so
    a val/test row's own (backward-looking) feature window cannot closely
    straddle a training row on the other side of the boundary."""
    tf_sec = _TF_SECONDS[tf]
    embargo = pd.Timedelta(seconds=embargo_bars * tf_sec)
    pts = dataset["prediction_timestamp"]

    train_raw = pts < fold.train_end
    val_raw = (pts >= fold.val_start + embargo) & (pts < fold.val_end)
    test_raw = (pts >= fold.test_start + embargo) & (pts < fold.test_end)

    train_purge = train_raw & (dataset["target_end_timestamp"] >= fold.train_end)
    val_purge = val_raw & (dataset["target_end_timestamp"] >= fold.val_end)

    train_mask = train_raw & ~train_purge
    val_mask = val_raw & ~val_purge
    test_mask = test_raw   # test is a terminal window; nothing after it to leak into

    report = {
        "fold": fold.fold, "n_train_raw": int(train_raw.sum()), "n_train_purged": int(train_purge.sum()),
        "n_val_raw": int(val_raw.sum()), "n_val_purged": int(val_purge.sum()),
        "n_train": int(train_mask.sum()), "n_val": int(val_mask.sum()), "n_test": int(test_mask.sum()),
        "embargo_bars": embargo_bars,
    }
    return dataset.loc[train_mask], dataset.loc[val_mask], dataset.loc[test_mask], report


def _cap_train_rows(train_df: pd.DataFrame, cap: int = _TRAIN_CAP_ROWS, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Computational bound (documented, not hidden): a systematic, seeded
    stride-subsample of an oversized TRAIN set, preserving chronological
    coverage rather than truncating to only the most recent rows."""
    n = len(train_df)
    if n <= cap:
        return train_df
    stride = n / cap
    idx = (np.arange(cap) * stride).astype(int)
    idx = np.clip(idx, 0, n - 1)
    return train_df.iloc[np.unique(idx)]


# ==========================================================================
# §9 baselines
# ==========================================================================
def baseline_majority_class(train: pd.DataFrame) -> float:
    """Constant probability = the majority class's TRAIN-set frequency."""
    p1 = float(train["target"].mean())
    return 1.0 if p1 >= 0.5 else 0.0


def baseline_persistence(train: pd.DataFrame) -> float:
    """§9 Baseline 2: predict future_HIGH = current_HIGH. Every V2 event row
    has current state = HIGH by construction (that IS the event definition),
    so this baseline is the CONSTANT predictor P(HIGH)=1.0 within this
    dataset -- not a modelling choice, a structural fact of the target's own
    definition, verified in §10/§19 of the documentation and by
    ``test_persistence_baseline_is_constant_in_this_population``."""
    return 1.0


def baseline_simple_volatility(train: pd.DataFrame, val_or_test: pd.DataFrame) -> np.ndarray:
    """§9 Baseline 3: a single-feature logistic rule on ``rv_rank`` alone,
    fit on TRAIN only. This is the ONLY baseline with genuine ranking power
    in this population (Baseline 1/2 are constants -> AUC=0.5 by
    construction), and is therefore the real "does full ML beat a trivial
    current-state rule" comparison (§10)."""
    X = train[["feat__rv_rank"]].to_numpy(float)
    y = train["target"].to_numpy(int)
    model = LogisticRegression(max_iter=200, random_state=RANDOM_SEED)
    model.fit(X, y)
    return model.predict_proba(val_or_test[["feat__rv_rank"]].to_numpy(float))[:, 1]


def baseline_random(n: int, seed: int = RANDOM_SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(0.0, 1.0, size=n)


# ==========================================================================
# §11/§12 models (no OOS tuning -- fixed, sensible defaults, no grid search)
# ==========================================================================
def _make_models() -> Dict[str, Any]:
    return {
        # Features span very different scales (hour 0-23 vs atr_ret ~1e-3), which
        # left the un-scaled lbfgs solver failing to converge within max_iter on
        # the first full run -- fixed with a StandardScaler step. Tree-based
        # models (RF/HGB) are scale-invariant and need no such fix.
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED,
                                       class_weight="balanced")),
        ]),
        "random_forest": RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=20,
                                                random_state=RANDOM_SEED, n_jobs=-1,
                                                class_weight="balanced"),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_depth=6, max_iter=150,
                                                                  random_state=RANDOM_SEED),
    }


# ==========================================================================
# §20 metrics
# ==========================================================================
def compute_metrics(y_true: np.ndarray, p_pred: np.ndarray) -> Dict[str, Any]:
    y_true = np.asarray(y_true, int)
    p_pred = np.clip(np.asarray(p_pred, float), 1e-6, 1 - 1e-6)
    out: Dict[str, Any] = {"n": int(len(y_true)), "positive_rate": round(float(y_true.mean()), 4)}
    if len(set(y_true.tolist())) < 2:
        out.update({"roc_auc": None, "pr_auc": None, "log_loss": None, "brier": None})
    else:
        out["roc_auc"] = round(float(roc_auc_score(y_true, p_pred)), 4)
        out["pr_auc"] = round(float(average_precision_score(y_true, p_pred)), 4)
        out["log_loss"] = round(float(log_loss(y_true, p_pred, labels=[0, 1])), 4)
        out["brier"] = round(float(brier_score_loss(y_true, p_pred)), 4)
    y_hat = (p_pred >= 0.5).astype(int)
    out["accuracy"] = round(float(accuracy_score(y_true, y_hat)), 4)
    out["balanced_accuracy"] = round(float(balanced_accuracy_score(y_true, y_hat)), 4)
    out["precision"] = round(float(precision_score(y_true, y_hat, zero_division=0)), 4)
    out["recall"] = round(float(recall_score(y_true, y_hat, zero_division=0)), 4)
    out["f1"] = round(float(f1_score(y_true, y_hat, zero_division=0)), 4)
    cm = confusion_matrix(y_true, y_hat, labels=[0, 1])
    out["confusion_matrix"] = {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]),
                               "fn": int(cm[1, 0]), "tp": int(cm[1, 1])}
    return out


def calibration_report(y_true: np.ndarray, p_pred: np.ndarray, n_bins: int = 10) -> Dict[str, Any]:
    y_true = np.asarray(y_true, int)
    p_pred = np.asarray(p_pred, float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(p_pred, bins) - 1, 0, n_bins - 1)
    rows = []
    ece = 0.0
    for b in range(n_bins):
        m = bin_idx == b
        if not m.any():
            continue
        mean_pred = float(p_pred[m].mean())
        mean_actual = float(y_true[m].mean())
        rows.append({"bin": b, "n": int(m.sum()), "mean_predicted": round(mean_pred, 4),
                    "mean_actual": round(mean_actual, 4)})
        ece += (m.sum() / len(y_true)) * abs(mean_pred - mean_actual)
    return {"bins": rows, "expected_calibration_error": round(float(ece), 4)}


# ==========================================================================
# Core fit/eval unit
# ==========================================================================
def fit_and_eval(train: pd.DataFrame, test: pd.DataFrame, feature_names: List[str],
                 model_name: str) -> Dict[str, Any]:
    train_c = _cap_train_rows(train)
    cols = [f"feat__{f}" for f in feature_names]
    Xtr = train_c[cols].to_numpy(float)
    ytr = train_c["target"].to_numpy(int)
    Xte = test[cols].to_numpy(float)
    yte = test["target"].to_numpy(int)
    model = _make_models()[model_name]
    model.fit(Xtr, ytr)
    p_te = model.predict_proba(Xte)[:, 1]
    metrics = compute_metrics(yte, p_te)
    cal = calibration_report(yte, p_te)
    return {"model": model_name, "features": feature_names, "n_train": int(len(train_c)),
           "n_train_capped_from": int(len(train)), "metrics": metrics, "calibration": cal,
           "_fitted_model": model, "_p_pred": p_te, "_y_true": yte}


# ==========================================================================
# §25/§26 permutation importance and §26 shuffled-target control
# ==========================================================================
def permutation_importance_report(fitted: Dict[str, Any], test: pd.DataFrame,
                                  feature_names: List[str], seed: int = RANDOM_SEED,
                                  max_rows: int = 3000) -> Dict[str, Any]:
    cols = [f"feat__{f}" for f in feature_names]
    sub = test.iloc[:max_rows] if len(test) > max_rows else test
    X = sub[cols].to_numpy(float)
    y = sub["target"].to_numpy(int)
    r = permutation_importance(fitted["_fitted_model"], X, y, n_repeats=8, random_state=seed,
                               scoring="roc_auc")
    return {f: round(float(m), 5) for f, m in zip(feature_names, r.importances_mean)}


def shuffled_target_control(train: pd.DataFrame, test: pd.DataFrame, feature_names: List[str],
                            model_name: str, seed: int = _SHUFFLE_SEED) -> Dict[str, Any]:
    """§26: features unchanged, TRAIN targets randomly shuffled before
    fitting. A properly-behaved pipeline should lose essentially all
    predictive skill (AUC -> ~0.5) on the (unshuffled) test set."""
    rng = np.random.default_rng(seed)
    train_shuf = train.copy()
    train_shuf["target"] = rng.permutation(train_shuf["target"].to_numpy())
    result = fit_and_eval(train_shuf, test, feature_names, model_name)
    return {"model": model_name, "metrics": result["metrics"]}


# ==========================================================================
# §27 placebo / condition-decoupled control (reuses Phase 79's methodology)
# ==========================================================================
def placebo_dataset(tf: str, horizon: int, n_events_target: int,
                    instruments: Tuple[str, ...] = INSTRUMENTS_V2, seed: int = _PLACEBO_SEED) -> pd.DataFrame:
    """A matched-count random (condition-decoupled) event set per instrument,
    built through the SAME ``build_dataset`` pipeline used for the real
    study -- only the event index array is replaced (§27)."""
    frames = []
    per_inst_n = max(20, n_events_target // max(1, len(instruments)))
    for k, inst in enumerate(instruments):
        df = load_bars(inst, tf)
        if df.empty or len(df) < 2000:
            continue
        df = augment(df, tf)
        n = len(df)
        eligible = np.arange(_WARMUP, max(_WARMUP + 1, n - max(ALL_HORIZONS) - 1))
        if len(eligible) < 20:
            continue
        rng = np.random.default_rng(seed + k)
        take = min(per_inst_n, len(eligible))
        idx = np.sort(rng.choice(eligible, size=take, replace=False))
        d = build_dataset(inst, tf, horizon, event_idx_override=idx)
        if not d.empty:
            frames.append(d)
    if not frames:
        return pd.DataFrame()
    pooled = pd.concat(frames, ignore_index=True)
    pooled["feat__instrument_code"] = pooled["instrument"].map(_INSTRUMENT_CODE)
    return pooled.sort_values("prediction_timestamp").reset_index(drop=True)


_MATCHED_PLACEBO_SHIFT_BARS = 200   # far beyond any horizon tested (max 8) -- decouples timing


def population_matched_placebo_targets(df_subset: pd.DataFrame, tf: str, horizon: int,
                                       shift_bars: int = _MATCHED_PLACEBO_SHIFT_BARS
                                       ) -> np.ndarray:
    """§27 placebo, corrected for a confound discovered empirically on the
    first Phase 80 run (documented in the doc's methodology-note section):
    ``placebo_dataset`` above draws events from the WHOLE series
    (rv_rank spanning ~0.0-1.0), whereas the real V2 study is conditioned on
    rv_rank > 0.66 (spanning only ~0.66-1.0). Because rv_rank is itself a
    feature, evaluating on the broader, unconditioned population is a
    strictly EASIER classification problem (this is exactly Phase 76's
    original, stronger, unconditioned volatility-clustering signal) --
    independent of whether the CONDITIONED V2 persistence effect is real.
    Confirmed empirically: the population-decoupled placebo's ablation-A
    (current-state-only) AUC (0.629) already exceeds the real dataset's
    ablation-A AUC (0.592) before any other feature is added -- a population
    difference, not a leakage signal.

    This function instead builds a POPULATION-MATCHED placebo: the exact
    same (train/test) feature rows as the real study (same instrument, same
    event_idx, hence IDENTICAL feature values and an identical rv_rank
    range), with ONLY the target relabelled using the outcome
    ``shift_bars`` further into the future than the true horizon --
    decoupling the genuine timing of the persistence relationship while
    holding the evaluated population exactly fixed. If a model's real skill
    is genuine, it should collapse toward chance here; if it were merely a
    population-breadth artifact, this control could not have detected that
    in the first place (which is precisely why it replaces, rather than
    supplements, the population-decoupled version for the ML gate, §35 Gate
    H)."""
    out = np.full(len(df_subset), np.nan)
    for inst in df_subset["instrument"].unique():
        df_bar = augment(load_bars(inst, tf), tf)
        rv_rank = df_bar["rv_rank"].to_numpy(float)
        n = len(df_bar)
        m = (df_subset["instrument"] == inst).to_numpy()
        idxs = df_subset.loc[m, "event_idx"].to_numpy()
        j = idxs + shift_bars + horizon
        valid = j < n
        vals = np.full(len(idxs), np.nan)
        vals[valid] = (rv_rank[j[valid]] > 0.66).astype(float)
        out[np.where(m)[0]] = vals
    return out


def population_matched_placebo_control(train: pd.DataFrame, test: pd.DataFrame,
                                       feature_names: List[str], model_name: str, tf: str,
                                       horizon: int, shift_bars: int = _MATCHED_PLACEBO_SHIFT_BARS
                                       ) -> Optional[Dict[str, Any]]:
    train2, test2 = train.copy(), test.copy()
    train2["target"] = population_matched_placebo_targets(train2, tf, horizon, shift_bars)
    test2["target"] = population_matched_placebo_targets(test2, tf, horizon, shift_bars)
    train2 = train2.dropna(subset=["target"])
    test2 = test2.dropna(subset=["target"])
    if len(train2) < 200 or len(test2) < 30:
        return None
    train2["target"] = train2["target"].astype(int)
    test2["target"] = test2["target"].astype(int)
    r = fit_and_eval(train2, test2, feature_names, model_name)
    return r["metrics"]


# ==========================================================================
# §28/§29 future-shock / rolling-window regression tools (mirrors Phase 79)
# ==========================================================================
def _synthetic_candles(n: int, seed: int, tf_sec: int = 900, t0: int = 1_650_000_000) -> List[Dict[str, Any]]:
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


def _dataset_from_rows(rows: List[Dict[str, Any]], tf: str, horizon: int,
                       instrument: str = "SYN") -> pd.DataFrame:
    with mock.patch.object(p76.store, "get_candles", lambda *_a, **_k: rows):
        return build_dataset(instrument, tf, horizon)


def check_feature_future_shock_invariance(tf: str = "15m", n: int = 3000, seed: int = 201,
                                          cutoff: int = 2500, shock_mult: float = 50.0,
                                          horizon: int = 4) -> Dict[str, Any]:
    """§28: identical history through ``cutoff``; a huge future bar inserted
    strictly after it. Every feature column for events at/before the cutoff
    must be identical, AND (§28 model invariant) a model trained on the
    normal dataset must produce IDENTICAL predictions for those same events
    whether evaluated against the normal or shocked feature table."""
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
    cols = [f"feat__{f}_a" for f in FEATURE_NAMES]
    feats_equal = True
    for f in FEATURE_NAMES:
        a = merged[f"feat__{f}_a"].to_numpy()
        b = merged[f"feat__{f}_b"].to_numpy()
        if not np.allclose(np.nan_to_num(a, nan=-9.9e30), np.nan_to_num(b, nan=-9.9e30), rtol=0, atol=1e-9):
            feats_equal = False
    pred_equal = True
    if len(merged) >= 30:
        model = _make_models()["logistic_regression"]
        cols_x = [f"feat__{f}" for f in FEATURE_NAMES]
        model.fit(common_a[cols_x].to_numpy(float), common_a["target"].to_numpy(int))
        pa = model.predict_proba(merged[[f"feat__{f}_a" for f in FEATURE_NAMES]].to_numpy(float))[:, 1]
        pb = model.predict_proba(merged[[f"feat__{f}_b" for f in FEATURE_NAMES]].to_numpy(float))[:, 1]
        pred_equal = bool(np.allclose(pa, pb, rtol=0, atol=1e-9))
    return {"n_common_events": int(len(merged)), "features_identical": feats_equal,
           "model_predictions_identical": pred_equal, "pass": bool(feats_equal and pred_equal)}


# ==========================================================================
# §30 determinism
# ==========================================================================
def _headline_fit_signature(tf: str, horizon: int, ablation: str, models: List[str],
                            pooled: pd.DataFrame, fold: Fold) -> str:
    train, _val, test, _report = split_fold(pooled, fold, tf)
    parts = []
    for m in models:
        r = fit_and_eval(train, test, ABLATION_SETS[ablation], m)
        parts.append({"model": m, "metrics": r["metrics"]})
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


# ==========================================================================
# §31 experiment record
# ==========================================================================
@dataclass
class ExperimentRecord:
    experiment_id: str
    target_version: str
    feature_schema_version: str
    dataset_version: str
    model_type: str
    ablation: str
    timeframe: str
    horizon_bars: int
    fold: int
    instrument_scope: str
    train_period: Dict[str, Any]
    validation_period: Dict[str, Any]
    oos_period: Dict[str, Any]
    purge_embargo: Dict[str, Any]
    metrics: Dict[str, Any]
    baseline_metrics: Dict[str, Any]
    git_commit: Optional[str]
    seed: int = RANDOM_SEED

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _git_commit() -> Optional[str]:
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


# ==========================================================================
# §35 model-value gates
# ==========================================================================
def evaluate_gates(headline: Dict[str, Any], leakage: Dict[str, Any], determinism_match: bool,
                   cross_asset: Dict[str, Any], cross_year: Dict[str, Any],
                   calibration_ece: float, placebo_auc: Optional[float],
                   real_auc: Optional[float]) -> Dict[str, Any]:
    gate_a_leakage = bool(leakage.get("all_pass"))
    gate_b_repro = bool(determinism_match)
    gate_c_baseline = bool(headline.get("ml_beats_simple_volatility_baseline"))
    gate_d_oos = bool(headline.get("oos_auc_above_half") is True)
    gate_e_cross_asset = bool(cross_asset.get("no_single_instrument_dominance"))
    gate_f_cross_year = bool(cross_year.get("consistent_across_periods"))
    gate_g_calibration = bool(calibration_ece is not None and calibration_ece < 0.15)
    gate_h_placebo = bool(placebo_auc is not None and real_auc is not None
                          and real_auc > placebo_auc + 0.05)
    gates = {"A_leakage": gate_a_leakage, "B_reproducibility": gate_b_repro,
            "C_baseline": gate_c_baseline, "D_oos": gate_d_oos,
            "E_cross_asset": gate_e_cross_asset, "F_cross_year": gate_f_cross_year,
            "G_calibration": gate_g_calibration, "H_placebo": gate_h_placebo}
    return {"gates": gates, "all_pass": all(gates.values()), "n_pass": sum(gates.values())}


def classify_verdict(gates: Dict[str, Any], headline: Dict[str, Any]) -> str:
    """§36 — exactly one of the three allowed outcomes, no invented alternative."""
    if not gates["gates"]["A_leakage"] or not gates["gates"]["B_reproducibility"]:
        # a leakage or reproducibility failure invalidates the whole pilot;
        # still not force-fit into one of the 3 semantic outcomes, but the
        # closest honest label is instability (the finding cannot be trusted).
        return "ML_PREDICTIVE_EDGE_UNSTABLE"
    if gates["all_pass"] and headline.get("beats_simple_baseline_materially"):
        return "ML_INCREMENTAL_VALUE_CONFIRMED"
    if not gates["gates"]["E_cross_asset"] or not gates["gates"]["F_cross_year"] or not gates["gates"]["D_oos"]:
        return "ML_PREDICTIVE_EDGE_UNSTABLE"
    return "TARGET_PREDICTABLE_BUT_NO_INCREMENTAL_ML_VALUE"


# ==========================================================================
# §17/§19/§26 cross-asset, cross-year (via fold test periods) helpers
# ==========================================================================
def cross_asset_report(fitted: Dict[str, Any], test: pd.DataFrame, feature_names: List[str]
                       ) -> Dict[str, Any]:
    """Per-instrument AUC of the POOLED model's predictions on that
    instrument's own slice of the test set (§17 'per-instrument'; the
    pooled-vs-per-instrument comparison IS the 'pooled' arm)."""
    per_inst = {}
    p_pred, y_true = fitted["_p_pred"], fitted["_y_true"]
    test = test.reset_index(drop=True)
    for inst in sorted(test["instrument"].unique()):
        m = (test["instrument"] == inst).to_numpy()
        if m.sum() < 30:
            per_inst[inst] = {"n": int(m.sum()), "state": "INSUFFICIENT_SAMPLE"}
            continue
        per_inst[inst] = compute_metrics(y_true[m], p_pred[m])
    aucs = [v["roc_auc"] for v in per_inst.values() if v.get("roc_auc") is not None]
    dominance = False
    if len(aucs) >= 2:
        # "no single instrument dominance": removing the single BEST-AUC
        # instrument from the average must not collapse the remaining mean AUC to <= 0.5
        best = max(aucs)
        rest = [a for a in aucs if a != best] or aucs
        dominance = (sum(rest) / len(rest)) <= 0.5
    return {"per_instrument": per_inst, "no_single_instrument_dominance": not dominance}


def leave_one_asset_out_report(pooled: pd.DataFrame, fold: Fold, tf: str, feature_names: List[str],
                               model_name: str, instruments: Tuple[str, ...] = INSTRUMENTS_V2
                               ) -> Dict[str, Any]:
    """§17 leave-one-asset-out: refit on all-but-one instrument's fold train,
    evaluate on the excluded instrument's own fold test."""
    train_all, _val, test_all, _rep = split_fold(pooled, fold, tf)
    out = {}
    for held_out in instruments:
        train_wo = train_all[train_all["instrument"] != held_out]
        test_held = test_all[test_all["instrument"] == held_out]
        if len(train_wo) < 500 or len(test_held) < 30:
            out[held_out] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        r = fit_and_eval(train_wo, test_held, feature_names, model_name)
        out[held_out] = {"n_test": len(test_held), "metrics": r["metrics"]}
    aucs = [v["metrics"]["roc_auc"] for v in out.values()
           if isinstance(v, dict) and v.get("metrics", {}).get("roc_auc") is not None]
    return {"per_instrument_held_out": out,
           "all_positive_auc_under_loo": bool(aucs) and all(a > 0.5 for a in aucs)}


def cross_year_from_folds(fold_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """§19: because each fold's TEST window IS a distinct calendar period
    (fold 1 -> H2 2023, fold 2 -> H2 2024, fold 3 -> H2 2025 onward), the
    walk-forward fold results already ARE the cross-year analysis -- no
    separate re-slicing needed (or possible without violating the OOS
    discipline, see the ``make_folds`` docstring)."""
    aucs = [f["metrics"]["roc_auc"] for f in fold_results if f["metrics"].get("roc_auc") is not None]
    consistent = bool(aucs) and all(a > 0.5 for a in aucs) and (max(aucs) - min(aucs) < 0.30)
    return {"per_fold_test_period_auc": [
        {"fold": f["fold"], "test_period_label": f.get("test_period_label"), "auc": f["metrics"].get("roc_auc")}
        for f in fold_results], "consistent_across_periods": consistent}


# ==========================================================================
# §26 experiment run
# ==========================================================================
@dataclass
class Phase80Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    phase79_commit_reference: Optional[str]
    target_version: str
    feature_schema_version: str
    dataset_version: str
    feature_registry: List[Dict[str, Any]]
    ablation_sets: Dict[str, List[str]]
    dataset_summary: Dict[str, Any]
    feature_target_contract: Dict[str, Any]
    folds: Dict[str, List[Dict[str, Any]]]
    baselines: Dict[str, Any]
    ablation_sweep: List[Dict[str, Any]]
    horizon_matrix: List[Dict[str, Any]]
    secondary_timeframe: List[Dict[str, Any]]
    cross_asset: Dict[str, Any]
    leave_one_asset_out: Dict[str, Any]
    cross_year: Dict[str, Any]
    permutation_importance: Dict[str, Any]
    controls: Dict[str, Any]
    calibration_headline: Dict[str, Any]
    determinism: Dict[str, Any]
    experiments: List[Dict[str, Any]]
    incremental_value: Dict[str, Any]
    gates: Dict[str, Any]
    verdict: str
    phase81_queue: List[Dict[str, Any]]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def run() -> Phase80Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()
    model_names = list(_make_models().keys())
    reference_model = "hist_gradient_boosting"

    # ---- §5/§6 datasets (15m: all 4 horizons; 1h: headline horizon only) --
    pooled_15m = {h: build_pooled_dataset(PRIMARY_TF, h) for h in ALL_HORIZONS}
    pooled_1h_h4 = build_pooled_dataset(SECONDARY_TF, PRIMARY_HORIZON)

    contract = {f"15m_h{h}": assert_feature_target_contract(pooled_15m[h]) for h in ALL_HORIZONS}
    contract["1h_h4"] = assert_feature_target_contract(pooled_1h_h4)
    leakage_all_pass = all(v.get("pass") for v in contract.values())

    dataset_summary = {
        "instruments": list(INSTRUMENTS_V2), "primary_timeframe": PRIMARY_TF,
        "secondary_timeframe": SECONDARY_TF, "primary_horizon": PRIMARY_HORIZON,
        "horizons": list(ALL_HORIZONS), "feature_count": len(FEATURE_NAMES),
        "feature_groups": FEATURE_GROUPS,
        "rows_by_horizon_15m": {f"h{h}": {"n_rows": int(len(pooled_15m[h])),
                                          "positive_rate": round(float(pooled_15m[h]["target"].mean()), 4)
                                          if len(pooled_15m[h]) else None} for h in ALL_HORIZONS},
        "rows_1h_h4": {"n_rows": int(len(pooled_1h_h4)),
                      "positive_rate": round(float(pooled_1h_h4["target"].mean()), 4)
                      if len(pooled_1h_h4) else None},
    }

    # ---- §13/§14 folds -----------------------------------------------------
    folds_15m = make_folds(pooled_15m[PRIMARY_HORIZON], _FOLD_BOUNDARY_YEARS)
    folds_1h = make_folds(pooled_1h_h4, _FOLD_BOUNDARY_YEARS_SECONDARY)
    folds_dict = {"15m": [f.to_dict() for f in folds_15m], "1h": [f.to_dict() for f in folds_1h]}
    _test_period_label = {1: "2023_H2", 2: "2024_H2", 3: "2025_H2_onward"}
    _test_period_label_1h = {1: "2024_H2", 2: "2025_H2_onward"}

    experiments: List[Dict[str, Any]] = []

    def _record(exp_id, model, ablation, tf, horizon, fold_obj, split_report, metrics, baseline_metrics,
               instrument_scope="pooled_6"):
        rec = ExperimentRecord(
            experiment_id=exp_id, target_version=TARGET_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION, dataset_version=DATASET_VERSION,
            model_type=model, ablation=ablation, timeframe=tf, horizon_bars=horizon,
            fold=fold_obj.fold, instrument_scope=instrument_scope,
            train_period={"end": fold_obj.train_end.isoformat()},
            validation_period={"start": fold_obj.val_start.isoformat(), "end": fold_obj.val_end.isoformat()},
            oos_period={"start": fold_obj.test_start.isoformat(), "end": fold_obj.test_end.isoformat()},
            purge_embargo=split_report, metrics=metrics, baseline_metrics=baseline_metrics,
            git_commit=git_commit)
        experiments.append(rec.to_dict())

    # ---- §9 baselines per 15m/h4 fold --------------------------------------
    baselines: Dict[str, Any] = {}
    for fold in folds_15m:
        train, val, test, rep = split_fold(pooled_15m[PRIMARY_HORIZON], fold, PRIMARY_TF)
        if len(train) < 200 or len(test) < 30:
            baselines[f"fold{fold.fold}"] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        y_test = test["target"].to_numpy(int)
        maj_p = baseline_majority_class(train)
        pers_p = baseline_persistence(train)
        simple_p = baseline_simple_volatility(train, test)
        rand_p = baseline_random(len(test), seed=RANDOM_SEED + fold.fold)
        baselines[f"fold{fold.fold}"] = {
            "test_period": _test_period_label[fold.fold],
            "majority_class": compute_metrics(y_test, np.full(len(test), maj_p)),
            "persistence": compute_metrics(y_test, np.full(len(test), pers_p)),
            "simple_volatility_rule": compute_metrics(y_test, simple_p),
            "random": compute_metrics(y_test, rand_p),
        }

    # ---- §24 ablation sweep: 15m, h4, all folds x all ablations x all models
    ablation_sweep: List[Dict[str, Any]] = []
    fold3_fits: Dict[Tuple[str, str], Dict[str, Any]] = {}   # (ablation, model) -> fitted, for reuse
    for fold in folds_15m:
        train, val, test, rep = split_fold(pooled_15m[PRIMARY_HORIZON], fold, PRIMARY_TF)
        if len(train) < 200 or len(test) < 30:
            continue
        for ablation, feats in ABLATION_SETS.items():
            for m in model_names:
                r = fit_and_eval(train, test, feats, m)
                row = {"fold": fold.fold, "test_period": _test_period_label[fold.fold],
                      "ablation": ablation, "n_features": len(feats), "model": m,
                      "n_train": r["n_train"], "n_test": len(test), "metrics": r["metrics"]}
                ablation_sweep.append(row)
                _record(f"v2-15m-h4-{ablation}-{m}-f{fold.fold}", m, ablation, PRIMARY_TF,
                       PRIMARY_HORIZON, fold, rep, r["metrics"], baselines.get(f"fold{fold.fold}", {}))
                if fold.fold == 3:
                    fold3_fits[(ablation, m)] = r
        del train, val, test
    gc.collect()

    # ---- §34 full horizon matrix: 15m, ablation D, all horizons x folds x models
    horizon_matrix: List[Dict[str, Any]] = []
    for h in ALL_HORIZONS:
        ds_h = pooled_15m[h]
        folds_h = folds_15m if h == PRIMARY_HORIZON else make_folds(ds_h, _FOLD_BOUNDARY_YEARS)
        for fold in folds_h:
            train, val, test, rep = split_fold(ds_h, fold, PRIMARY_TF)
            if len(train) < 200 or len(test) < 30:
                continue
            if h == PRIMARY_HORIZON:
                # reuse the ablation-D fits already computed above (no duplicate compute)
                for m in model_names:
                    r = fold3_fits.get((ABLATION_D := "D_full_conservative", m)) if fold.fold == 3 else None
                    metrics = r["metrics"] if r else next(
                        (row["metrics"] for row in ablation_sweep
                         if row["fold"] == fold.fold and row["ablation"] == "D_full_conservative" and row["model"] == m),
                        None)
                    if metrics:
                        horizon_matrix.append({"horizon": h, "fold": fold.fold,
                                              "test_period": _test_period_label[fold.fold],
                                              "model": m, "metrics": metrics})
                continue
            for m in model_names:
                r = fit_and_eval(train, test, ABLATION_SETS["D_full_conservative"], m)
                horizon_matrix.append({"horizon": h, "fold": fold.fold,
                                      "test_period": _test_period_label[fold.fold],
                                      "model": m, "metrics": r["metrics"]})
                _record(f"v2-15m-h{h}-D_full_conservative-{m}-f{fold.fold}", m, "D_full_conservative",
                       PRIMARY_TF, h, fold, rep, r["metrics"], {})
            del train, val, test
    gc.collect()

    # ---- §18 secondary timeframe (1h, h4, ablation D, all models) ---------
    secondary_timeframe: List[Dict[str, Any]] = []
    for fold in folds_1h:
        train, val, test, rep = split_fold(pooled_1h_h4, fold, SECONDARY_TF)
        if len(train) < 200 or len(test) < 30:
            continue
        for m in model_names:
            r = fit_and_eval(train, test, ABLATION_SETS["D_full_conservative"], m)
            secondary_timeframe.append({"fold": fold.fold, "test_period": _test_period_label_1h[fold.fold],
                                        "model": m, "n_train": r["n_train"], "n_test": len(test),
                                        "metrics": r["metrics"]})
            _record(f"v2-1h-h4-D_full_conservative-{m}-f{fold.fold}", m, "D_full_conservative",
                   SECONDARY_TF, PRIMARY_HORIZON, fold, rep, r["metrics"], {}, instrument_scope="pooled_6")

    # ---- headline reference fit (fold 3, 15m, h4, ablation D, reference model)
    headline_fold = folds_15m[-1]
    headline_train, _hv, headline_test, headline_split_report = split_fold(
        pooled_15m[PRIMARY_HORIZON], headline_fold, PRIMARY_TF)
    headline_fit = fold3_fits.get(("D_full_conservative", reference_model)) or fit_and_eval(
        headline_train, headline_test, ABLATION_SETS["D_full_conservative"], reference_model)

    # ---- §17 cross-asset + leave-one-asset-out (headline fold/model) ------
    cross_asset = cross_asset_report(headline_fit, headline_test, ABLATION_SETS["D_full_conservative"])
    loo = leave_one_asset_out_report(pooled_15m[PRIMARY_HORIZON], headline_fold, PRIMARY_TF,
                                     ABLATION_SETS["D_full_conservative"], reference_model)

    # ---- §19 cross-year (== the walk-forward fold test periods) -----------
    fold_level_headline = [row for row in ablation_sweep
                           if row["ablation"] == "D_full_conservative" and row["model"] == reference_model]
    for row in fold_level_headline:
        row["test_period_label"] = row["test_period"]
    cross_year = cross_year_from_folds([{**row, "test_period_label": row["test_period"]}
                                        for row in fold_level_headline])

    # ---- §25 permutation importance (one per fold, ablation D, ref model) -
    perm_importance: Dict[str, Any] = {}
    for fold in folds_15m:
        fit = fold3_fits.get(("D_full_conservative", reference_model)) if fold.fold == 3 else None
        if fit is None:
            train, val, test, rep = split_fold(pooled_15m[PRIMARY_HORIZON], fold, PRIMARY_TF)
            if len(train) < 200 or len(test) < 30:
                continue
            fit = fit_and_eval(train, test, ABLATION_SETS["D_full_conservative"], reference_model)
            test_for_perm = test
        else:
            test_for_perm = headline_test
        perm_importance[f"fold{fold.fold}"] = permutation_importance_report(
            fit, test_for_perm, ABLATION_SETS["D_full_conservative"])

    # ---- §26/§27 controls ---------------------------------------------------
    shuffled = shuffled_target_control(headline_train, headline_test,
                                       ABLATION_SETS["D_full_conservative"], reference_model)
    n_real_events = int(len(pooled_15m[PRIMARY_HORIZON][
        pooled_15m[PRIMARY_HORIZON]["prediction_timestamp"] < headline_fold.train_end]))
    placebo_ds = placebo_dataset(PRIMARY_TF, PRIMARY_HORIZON, n_real_events)
    placebo_metrics = None
    if not placebo_ds.empty:
        p_train, _pv, p_test, _prep = split_fold(placebo_ds, headline_fold, PRIMARY_TF)
        if len(p_train) >= 200 and len(p_test) >= 30:
            p_r = fit_and_eval(p_train, p_test, ABLATION_SETS["D_full_conservative"], reference_model)
            placebo_metrics = p_r["metrics"]
    # §27, corrected: the population-decoupled placebo above draws from the
    # WHOLE series (rv_rank ~0-1), a strictly EASIER population than the real
    # study's rv_rank>0.66 conditioning -- confirmed empirically (its own
    # ablation-A AUC of 0.629 already exceeds the real data's 0.592 before any
    # other feature is added). Kept for transparency, but NOT used for Gate H;
    # replaced by a population-MATCHED placebo (identical feature rows, target
    # relabelled from `shift_bars` further in the future) as the actual
    # decoupling evidence -- see `population_matched_placebo_control`.
    matched_placebo_full = population_matched_placebo_control(
        headline_train, headline_test, ABLATION_SETS["D_full_conservative"], reference_model,
        PRIMARY_TF, PRIMARY_HORIZON)
    matched_placebo_current_state = population_matched_placebo_control(
        headline_train, headline_test, ABLATION_SETS["A_current_state_only"], reference_model,
        PRIMARY_TF, PRIMARY_HORIZON)
    future_shock = check_feature_future_shock_invariance()

    controls = {
        "shuffled_target": shuffled,
        "placebo_decoupled_events_CONFOUNDED_diagnostic_only": {
            "n_events_used": n_real_events, "metrics": placebo_metrics,
            "note": "population-decoupled (whole-series) placebo -- confirmed CONFOUNDED by "
                   "population breadth (rv_rank spans ~0-1 vs the real study's ~0.66-1), NOT "
                   "used for Gate H; see population_matched_placebo instead"},
        "population_matched_placebo": {
            "shift_bars": _MATCHED_PLACEBO_SHIFT_BARS,
            "full_feature_set": matched_placebo_full,
            "current_state_only": matched_placebo_current_state,
            "note": "same feature ROWS as the real headline fit (identical rv_rank range); "
                   "only the target is relabelled using the outcome shift_bars further into "
                   "the future -- decouples the true short-horizon timing while holding the "
                   "evaluated population fixed"},
        "future_shock_invariance": future_shock,
    }

    # ---- §30 determinism: rerun the headline config (fold3, ablation D, all models) twice
    sig_a = _headline_fit_signature(PRIMARY_TF, PRIMARY_HORIZON, "D_full_conservative", model_names,
                                    pooled_15m[PRIMARY_HORIZON], headline_fold)
    sig_b = _headline_fit_signature(PRIMARY_TF, PRIMARY_HORIZON, "D_full_conservative", model_names,
                                    pooled_15m[PRIMARY_HORIZON], headline_fold)
    determinism = {"headline_signature_a": sig_a, "headline_signature_b": sig_b, "match": sig_a == sig_b}

    calibration_headline = headline_fit["calibration"]

    # ---- §10 incremental value ----------------------------------------------
    headline_auc = headline_fit["metrics"].get("roc_auc")
    simple_vol_p = baseline_simple_volatility(headline_train, headline_test)
    simple_vol_metrics = compute_metrics(headline_test["target"].to_numpy(int), simple_vol_p)
    ablation_a_auc = fold3_fits.get(("A_current_state_only", reference_model), {}).get(
        "metrics", {}).get("roc_auc")
    ablation_d_auc = headline_auc
    matched_placebo_d_auc = (matched_placebo_full or {}).get("roc_auc")
    matched_placebo_a_auc = (matched_placebo_current_state or {}).get("roc_auc")
    genuine_timing_effect_full = (round(ablation_d_auc - matched_placebo_d_auc, 4)
                                  if ablation_d_auc and matched_placebo_d_auc else None)
    genuine_timing_effect_current_state = (round(ablation_a_auc - matched_placebo_a_auc, 4)
                                           if ablation_a_auc and matched_placebo_a_auc else None)
    incremental_value = {
        "headline_fold": 3, "headline_test_period": _test_period_label[3],
        "reference_model": reference_model,
        "ml_full_auc": ablation_d_auc,
        "ml_current_state_only_auc": ablation_a_auc,
        "simple_volatility_baseline_auc": simple_vol_metrics.get("roc_auc"),
        "persistence_baseline_auc": 0.5,           # constant predictor, structural (§9 baseline_persistence)
        "majority_class_baseline_auc": 0.5,        # constant predictor, structural
        "matched_placebo_full_auc": matched_placebo_d_auc,
        "matched_placebo_current_state_only_auc": matched_placebo_a_auc,
        "genuine_timing_effect_full": genuine_timing_effect_full,
        "genuine_timing_effect_current_state_only": genuine_timing_effect_current_state,
        "delta_full_vs_current_state_only": (round(ablation_d_auc - ablation_a_auc, 4)
                                             if ablation_d_auc and ablation_a_auc else None),
        "delta_full_vs_simple_volatility": (round(ablation_d_auc - simple_vol_metrics["roc_auc"], 4)
                                            if ablation_d_auc and simple_vol_metrics.get("roc_auc") else None),
        "ml_beats_simple_volatility_baseline": bool(
            ablation_d_auc and simple_vol_metrics.get("roc_auc")
            and ablation_d_auc > simple_vol_metrics["roc_auc"] + 0.02),
        "beats_simple_baseline_materially": bool(
            ablation_d_auc and simple_vol_metrics.get("roc_auc")
            and ablation_d_auc > simple_vol_metrics["roc_auc"] + 0.05),
        "full_feature_set_adds_genuine_timing_value_beyond_current_state": bool(
            genuine_timing_effect_full is not None and genuine_timing_effect_current_state is not None
            and genuine_timing_effect_full > genuine_timing_effect_current_state + 0.02),
        "oos_auc_above_half": bool(ablation_d_auc and ablation_d_auc > 0.5),
        "interpretation": (
            "Most of the full model's headline AUC advantage over the current-state-only "
            "model persists even when the true short-horizon timing is broken (population-"
            "matched placebo), meaning it is NOT primarily a genuine short-horizon predictive "
            "skill -- it is largely explained by slower, more diffuse structure (session/regime/"
            "candle-shape patterns correlated with generic volatility levels) that the matched-"
            "placebo control also picks up. The 'beyond persistence' AUC gain (delta_full_vs_"
            "current_state_only) should NOT be read as evidence of a validated short-horizon "
            "ML edge without this caveat."),
    }

    # ---- §35 gates + §36 verdict --------------------------------------------
    leakage = {"all_pass": leakage_all_pass, "detail": contract}
    real_auc = ablation_d_auc
    placebo_auc = matched_placebo_d_auc   # the population-MATCHED placebo is the valid Gate-H input
    gates = evaluate_gates(incremental_value, leakage, determinism["match"], cross_asset, cross_year,
                           calibration_headline["expected_calibration_error"], placebo_auc, real_auc)
    verdict = classify_verdict(gates, incremental_value)

    # ---- §49 Phase 81 queue --------------------------------------------------
    phase81_queue: List[Dict[str, Any]] = []
    if verdict == "ML_INCREMENTAL_VALUE_CONFIRMED":
        phase81_queue.append({"item": "Extended walk-forward robustness validation for the V2 "
                              "volatility-regime ML model", "scope": "more folds / rolling "
                              "windows; still no trading integration"})
        phase81_queue.append({"item": "Instantiate the same reusable framework for V1 "
                              "(15m compression-duration -> range persistence)",
                              "scope": "target adapter + feature configuration only, per §49"})
    elif verdict == "TARGET_PREDICTABLE_BUT_NO_INCREMENTAL_ML_VALUE":
        phase81_queue.append({"item": "Investigate whether the persistence/simple-volatility "
                              "baseline alone is sufficient as a market-context feature",
                              "scope": "no further ML model development for V2"})
    else:
        phase81_queue.append({"item": "Return V2 ML experimentation to research; do not "
                              "re-tune the current pipeline against these OOS results",
                              "scope": "record as a negative/unstable result"})
    phase81_queue = phase81_queue[:3]

    ident = json.dumps({
        "schema": SCHEMA_VERSION, "verdict": verdict, "gates": gates["gates"],
        "incremental_value": incremental_value,
        "ablation_sweep": [{k: v for k, v in row.items()} for row in ablation_sweep],
    }, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase80Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        phase79_commit_reference=(p79.get_result() or {}).get("git_commit"),
        target_version=TARGET_VERSION, feature_schema_version=FEATURE_SCHEMA_VERSION,
        dataset_version=DATASET_VERSION, feature_registry=feature_registry_dicts(),
        ablation_sets=ABLATION_SETS, dataset_summary=dataset_summary,
        feature_target_contract=contract, folds=folds_dict, baselines=baselines,
        ablation_sweep=ablation_sweep, horizon_matrix=horizon_matrix,
        secondary_timeframe=secondary_timeframe, cross_asset=cross_asset,
        leave_one_asset_out=loo, cross_year=cross_year, permutation_importance=perm_importance,
        controls=controls, calibration_headline=calibration_headline, determinism=determinism,
        experiments=experiments, incremental_value=incremental_value, gates=gates, verdict=verdict,
        phase81_queue=phase81_queue, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase80Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase80_ml_volatility_regime", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 80 - ML volatility regime prediction pilot ...", flush=True)
    res = run()
    print(f"\n=== PHASE 80 ({res.runtime_seconds}s) ===")
    print(f"Dataset summary: {json.dumps(res.dataset_summary, default=str)}")
    print(f"\nHeadline incremental value: {json.dumps(res.incremental_value, default=str)}")
    print(f"\nGates: {json.dumps(res.gates, default=str)}")
    matched = res.controls["population_matched_placebo"]
    print(f"\nControls: shuffled={res.controls['shuffled_target']['metrics'].get('roc_auc')} "
         f"matched_placebo_full={(matched['full_feature_set'] or {}).get('roc_auc')} "
         f"matched_placebo_current_state={(matched['current_state_only'] or {}).get('roc_auc')} "
         f"future_shock_pass={res.controls['future_shock_invariance']['pass']}")
    print(f"\nDeterminism match: {res.determinism['match']}")
    print(f"\nVERDICT: {res.verdict}")
    print(f"\nPHASE 81 QUEUE ({len(res.phase81_queue)}):")
    for q in res.phase81_queue:
        print(f"  {q}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "FeatureSpec", "FEATURE_REGISTRY", "feature_registry_dicts", "FEATURE_GROUPS",
    "ABLATION_SETS", "build_dataset", "build_pooled_dataset",
    "assert_feature_target_contract", "Fold", "make_folds", "split_fold",
    "baseline_majority_class", "baseline_persistence", "baseline_simple_volatility",
    "baseline_random", "compute_metrics", "calibration_report", "fit_and_eval",
    "permutation_importance_report", "shuffled_target_control", "placebo_dataset",
    "check_feature_future_shock_invariance", "ExperimentRecord", "evaluate_gates",
    "classify_verdict", "ARTIFACT_KEY", "SCHEMA_VERSION", "TARGET_VERSION",
    "DATASET_VERSION", "FEATURE_SCHEMA_VERSION", "PRIMARY_TF", "SECONDARY_TF",
    "PRIMARY_HORIZON", "ALL_HORIZONS", "INSTRUMENTS_V2",
]
