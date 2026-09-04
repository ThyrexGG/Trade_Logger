# -*- coding: utf-8 -*-
"""
Phase 83 — Conditional Market Structure & Regime Interaction Discovery.

A research-INTEGRITY phase, not a strategy phase. V1 and V2 are CLOSED
(Phase 81: `V2_EXPLAINED_BY_TIME_AND_VOLATILITY`; Phase 82:
`V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT`) and are NOT reopened here — no
compression-run event, no HIGH-volatility-bucket event, no V1/V2 target
formula gated on either event is used. Phase 83 asks a different question:

    Do combinations of already-existing, already-causal market-context
    variables (volatility state, trend regime, session, momentum, location
    in recent range, distance from structural levels) reveal conditional
    market behavior that is NOT already explained by those variables' own
    main effects?

§0 ARCHITECTURE NOTE — WHAT IS REUSED AND WHY
------------------------------------------------------------------
Every context variable here is an EXISTING, already-causal column produced
by `phase76_event_study.load_bars` / `phase78_market_behavior_discovery_ii.
augment` — no new feature-engineering exercise, no technical-indicator
mining (§39 of the master prompt):
    - volatility state:  `atr_rank`, `rv_rank` (trailing-200-bar percentile
      ranks, both already causal)
    - trend/regime:      `regime` (Kaufman efficiency-ratio classification,
      Phase 76, already causal) and `eff` (the underlying continuous ratio)
    - session/time:      `session`, `hour`, `date` (Phase 76)
    - location:          `roll_h20`/`roll_l20` (Phase 78's shift(1)-excluded
      prior-20-bar structural range) -> a location-in-range measure
    - structure:         `pdh`/`pdl` (Phase 76's shift(1) previous-day
      high/low) -> distance-from-structural-level measures
    - momentum:          derived from `close`/`atr_ret` exactly as Phase 78's
      own price-feature family (`ret_4`-style ATR-normalised return)

Also reused, unchanged: `phase76_event_study.load_bars`,
`block_bootstrap`, `_benjamini_hochberg`, `_norm_cdf`, `ALL_INSTRUMENTS`,
`FWD_HORIZONS`; `phase80_ml_volatility_regime.make_folds`/`split_fold`
(calendar-year purged walk-forward, unchanged); `phase81_v2_information_
decomposition.bootstrap_metric_ci`/`bootstrap_delta_ci` (generic block-
bootstrap for an arbitrary metric); `phase82_compression_expansion_ml_
pilot`'s regression-metric conventions (OOS R^2 against the TRAIN mean,
Ridge as the primary interpretable model).

The ONLY new code is: (1) the TWO general-purpose targets (§3 -- neither
is event-gated, both are evaluated at EVERY bar, so neither reopens V1's
compression-conditioned target or V2's HIGH-bucket-conditioned target,
even though the underlying return/range MEASUREMENTS are the project's
established ones); (2) the fixed "strong context" baseline and the 5
pre-registered interaction candidates; (3) the interaction-specific
statistical machinery (categorical x continuous interaction terms,
discovery/confirmation temporal split, wrong-context placebo).

§3 TARGETS (small, pre-declared, §9/§10 of the master prompt)
------------------------------------------------------------------
T1 (directional): ATR-normalised forward signed return,
    `log(close[i+h]/close[i]) / atr_ret[i]`, evaluated at EVERY bar `i`
    (Phase 76's own `study_events` signed formula, reused, NOT event-gated).
T2 (magnitude):  ATR-normalised forward realized-range ratio,
    `(sum(tr, i+1..i+h)) / (atr_stable[i] * h) - 1`, evaluated at EVERY bar
    `i` (Phase 78's `study_range_expansion` formula, reused, NOT event-
    gated -- V1 is the SAME formula CONDITIONED on the compression event;
    here it is unconditional, a different research question).
Both use `h` in the unchanged `FWD_HORIZONS = (1, 2, 4, 8)`, headline h=4.

§14 DISCOVERY / CONFIRMATION SPLIT
------------------------------------------------------------------
DISCOVERY = all bars with `prediction_timestamp < 2025-01-01`.
CONFIRMATION = all bars with `prediction_timestamp >= 2025-07-01` (the
SAME "2025 H2 onward" fold-3 test window Phases 80-82 have used
throughout, chosen for consistency, not cherry-picked here). The gap
between them (2025 H1) is a purge/embargo buffer identical in spirit to
`phase80_ml_volatility_regime.make_folds`'s val/test structure. The
CONFIRMATION set is touched EXACTLY ONCE, after every candidate's
hypothesis, interaction columns, and thresholds are frozen from DISCOVERY
alone -- never used to reselect, re-bin, or retune anything.

This is independent of, and does not touch, the frozen Phase-74 Gold
holdout (`xauusd_market_conditions.FROZEN_CONTRACT_HASH`), which remains
completely unread throughout, as in every prior phase.

Read-only. No execution/broker/risk/forward-validation module imported.
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
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
import phase80_ml_volatility_regime as p80
import phase82_compression_expansion_ml_pilot as p82
from phase76_event_study import (
    ALL_INSTRUMENTS, FWD_HORIZONS, RANDOM_SEED, _benjamini_hochberg,
    _norm_cdf, block_bootstrap, load_bars,
)
from phase78_market_behavior_discovery_ii import augment
from phase80_ml_volatility_regime import Fold, _TF_SECONDS, make_folds, split_fold
from phase81_v2_information_decomposition import bootstrap_delta_ci, bootstrap_metric_ci
from phase82_compression_expansion_ml_pilot import compute_regression_metrics

SCHEMA_VERSION = "phase83.1"
ARTIFACT_KEY = "phase83_conditional_interaction_discovery"
DATASET_VERSION = "phase83-context-dataset-v1"
FEATURE_SCHEMA_VERSION = "phase83-features-v1"

PRIMARY_TF = "15m"
SECONDARY_TF = "1h"
PRIMARY_HORIZON = 4
ALL_HORIZONS: Tuple[int, ...] = FWD_HORIZONS       # (1, 2, 4, 8), unchanged
INSTRUMENTS_83: Tuple[str, ...] = ALL_INSTRUMENTS   # unchanged 6-instrument universe
_WARMUP = 200

_DISCOVERY_CUTOFF = pd.Timestamp("2025-01-01", tz="UTC")
_CONFIRMATION_START = pd.Timestamp("2025-07-01", tz="UTC")   # matches Phases 80-82's fold-3 test start

_GATE_MATERIAL_R2_MARGIN = 0.01     # reused verbatim from Phase 82's Gate-H R^2 margin
_SHUFFLE_SEED = 83001
_PLACEBO_SEED = 83002
_MIN_CELL_N = 200


# ==========================================================================
# §12/§13 pre-registered interaction matrix (5 candidates, small, fixed)
# ==========================================================================
_REGIME_LEVELS = ("TRENDING", "RANGING")           # MIXED is the dropped reference level
_SESSION_LEVELS = ("LONDON", "NEW_YORK", "LONDON_NY_OVERLAP", "LATE_US")  # TOKYO is reference

INTERACTION_CANDIDATES: List[Dict[str, Any]] = [
    {"id": "I1_VOLATILITY_x_TREND", "a": "atr_rank", "b": "regime", "b_type": "categorical",
    "target": "T2", "hypothesis": "Forward range expansion's relationship with current "
    "volatility state differs by trend regime (trending vs. ranging vs. mixed)."},
    {"id": "I2_VOLATILITY_x_SESSION", "a": "atr_rank", "b": "session", "b_type": "categorical",
    "target": "T2", "hypothesis": "Volatility's relationship with forward range differs by "
    "session (Tokyo/London/NY/overlap/late-US)."},
    {"id": "I3_MOMENTUM_x_VOLATILITY", "a": "mom_4", "b": "atr_rank", "b_type": "continuous",
    "target": "T1", "hypothesis": "Recent momentum's relationship with forward directional "
    "return differs between high- and low-volatility states (continuation vs. reversion)."},
    {"id": "I4_LOCATION_x_TREND", "a": "loc_in_range", "b": "regime", "b_type": "categorical",
    "target": "T1", "hypothesis": "Location within the recent 20-bar range predicts forward "
    "direction differently depending on trend regime (mean-reversion in ranges, "
    "continuation in trends)."},
    {"id": "I5_STRUCTURE_x_VOLATILITY", "a": "dist_pdh_atr", "b": "atr_rank", "b_type": "continuous",
    "target": "T2", "hypothesis": "Distance from the previous day's high (in ATR units) "
    "predicts forward range differently depending on current volatility state."},
]
N_PRIMARY_CANDIDATES = len(INTERACTION_CANDIDATES)


def interaction_registry_dicts() -> List[Dict[str, Any]]:
    return [{k: v for k, v in c.items()} for c in INTERACTION_CANDIDATES]


# §11 fixed "strong context" baseline -- SAME columns for every candidate,
# already includes every candidate's own main-effect variables (A and B),
# so the central per-candidate test (§19/§30/§54) reduces cleanly to
# "baseline D" vs. "baseline D + this candidate's A x B interaction term(s)".
BASELINE_D_CONTINUOUS = ("atr_rank", "rv_rank", "mom_4", "loc_in_range", "dist_pdh_atr",
                        "dist_pdl_atr", "hour_sin", "hour_cos", "dow")
BASELINE_D_REGIME_DUMMIES = tuple(f"regime_{r}" for r in _REGIME_LEVELS)
BASELINE_D_SESSION_DUMMIES = tuple(f"session_{s}" for s in _SESSION_LEVELS)
BASELINE_D_COLUMNS = (BASELINE_D_CONTINUOUS + BASELINE_D_REGIME_DUMMIES + BASELINE_D_SESSION_DUMMIES)


# ==========================================================================
# §0 causal feature builder -- every value at bar i derived from EXISTING
# causal columns in df[..i] only (nothing new computed beyond simple,
# already-causal transforms of atr_rank/rv_rank/regime/session/hour/
# roll_h20/roll_l20/pdh/pdl/close/atr/atr_ret, all pre-existing)
# ==========================================================================
def _build_context_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].to_numpy(float)
    n = len(df)
    atr = df["atr"].to_numpy(float)
    atr_ret = df["atr_ret"].to_numpy(float)
    atr_safe = np.where(atr > 0, atr, np.nan)

    mom_4 = np.full(n, np.nan)
    mom_4[4:] = np.log(c[4:] / c[:-4]) / np.where(atr_ret[4:] > 0, atr_ret[4:], np.nan)

    roll_h = df["roll_h20"].to_numpy(float)
    roll_l = df["roll_l20"].to_numpy(float)
    rng = roll_h - roll_l
    rng_safe = np.where(rng > 1e-12, rng, np.nan)
    loc_in_range = (c - roll_l) / rng_safe

    pdh = df["pdh"].to_numpy(float)
    pdl = df["pdl"].to_numpy(float)
    dist_pdh_atr = (pdh - c) / atr_safe
    dist_pdl_atr = (c - pdl) / atr_safe

    hour = df["hour"].to_numpy(float)
    dow = np.array([d.weekday() for d in df["date"].to_numpy()], float)

    out = pd.DataFrame({
        "atr_rank": df["atr_rank"].to_numpy(float), "rv_rank": df["rv_rank"].to_numpy(float),
        "mom_4": mom_4, "loc_in_range": loc_in_range,
        "dist_pdh_atr": dist_pdh_atr, "dist_pdl_atr": dist_pdl_atr,
        "hour_sin": np.sin(2 * np.pi * hour / 24.0), "hour_cos": np.cos(2 * np.pi * hour / 24.0),
        "dow": dow,
    })
    for r in _REGIME_LEVELS:
        out[f"regime_{r}"] = (df["regime"].to_numpy() == r).astype(float)
    for s in _SESSION_LEVELS:
        out[f"session_{s}"] = (df["session"].to_numpy() == s).astype(float)
    return out


# ==========================================================================
# §3 targets -- reused formulas, evaluated at EVERY bar (not event-gated)
# ==========================================================================
def _t1_signed_return(df: pd.DataFrame, horizon: int) -> np.ndarray:
    c = df["close"].to_numpy(float)
    ar = df["atr_ret"].to_numpy(float)
    n = len(df)
    out = np.full(n, np.nan)
    valid = np.arange(n - horizon)
    ok = np.isfinite(ar[valid]) & (ar[valid] > 0)
    vi = valid[ok]
    out[vi] = np.log(c[vi + horizon] / c[vi]) / ar[vi]
    return out


def _t2_range_ratio(df: pd.DataFrame, horizon: int) -> np.ndarray:
    tr = df["tr"].to_numpy(float)
    atr_stable = df["atr_stable"].to_numpy(float)
    n = len(df)
    csum = np.concatenate([[0.0], np.cumsum(tr)])
    out = np.full(n, np.nan)
    valid = np.arange(n - horizon)
    ok = np.isfinite(atr_stable[valid]) & (atr_stable[valid] > 0)
    vi = valid[ok]
    fut = csum[vi + horizon + 1] - csum[vi + 1]
    out[vi] = fut / (atr_stable[vi] * horizon) - 1.0
    return out


# ==========================================================================
# §6 dataset builder -- one row per bar (NOT event-gated), all horizons
# ==========================================================================
def build_context_dataset(instrument: str, tf: str, horizon: int = PRIMARY_HORIZON) -> pd.DataFrame:
    df = load_bars(instrument, tf)
    if df.empty or len(df) < 2000:
        return pd.DataFrame()
    df = augment(df, tf)
    n = len(df)
    feats = _build_context_features(df)
    t1 = _t1_signed_return(df, horizon)
    t2 = _t2_range_ratio(df, horizon)

    idx = np.arange(_WARMUP, n - horizon)
    finite_mask = np.isfinite(feats.iloc[idx].to_numpy(float)).all(axis=1) \
        & np.isfinite(t1[idx]) & np.isfinite(t2[idx])
    idx = idx[finite_mask]
    if len(idx) == 0:
        return pd.DataFrame()

    tf_sec = _TF_SECONDS[tf]
    open_ts = df["t"].to_numpy(np.int64)
    pred_ts = pd.to_datetime(open_ts[idx].astype(np.int64) + tf_sec, unit="s", utc=True)
    targ_end_ts = pd.to_datetime(open_ts[idx + horizon].astype(np.int64) + tf_sec, unit="s", utc=True)

    out = pd.DataFrame({
        "instrument": instrument, "timeframe": tf, "horizon_bars": horizon,
        "event_idx": idx, "target_idx": idx + horizon,
        "prediction_timestamp": pred_ts, "target_end_timestamp": targ_end_ts,
        "T1": t1[idx], "T2": t2[idx],
        "dataset_version": DATASET_VERSION, "feature_schema_version": FEATURE_SCHEMA_VERSION,
    })
    feat_rows = feats.iloc[idx].reset_index(drop=True)
    return pd.concat([out, feat_rows.add_prefix("feat__")], axis=1)


_INSTRUMENT_CODE = {inst: float(k) for k, inst in enumerate(INSTRUMENTS_83)}


def build_pooled_context_dataset(tf: str = PRIMARY_TF, horizon: int = PRIMARY_HORIZON,
                                 instruments: Tuple[str, ...] = INSTRUMENTS_83) -> pd.DataFrame:
    frames = [d for inst in instruments if not (d := build_context_dataset(inst, tf, horizon)).empty]
    if not frames:
        return pd.DataFrame()
    pooled = pd.concat(frames, ignore_index=True)
    pooled["feat__instrument_code"] = pooled["instrument"].map(_INSTRUMENT_CODE)
    return pooled.sort_values("prediction_timestamp").reset_index(drop=True)


def assert_feature_target_contract(dataset: pd.DataFrame, target_col: str = "T2") -> Dict[str, Any]:
    """§10 -- generic timestamp contract, adapted from Phase 80's (target
    column is parameterised since this module has two targets)."""
    if dataset.empty:
        return {"state": "NO_ROWS"}
    tf_sec = dataset["timeframe"].map(_TF_SECONDS)
    gap = (dataset["target_end_timestamp"] - dataset["prediction_timestamp"]).dt.total_seconds()
    min_expected = dataset["horizon_bars"] * tf_sec
    ok_after = bool((dataset["target_end_timestamp"] > dataset["prediction_timestamp"]).all())
    ok_min_gap = bool((gap.to_numpy() >= min_expected.to_numpy() - 1e-6).all())
    ok_target_finite = bool(np.isfinite(dataset[target_col].to_numpy()).all())
    return {"n_rows": int(len(dataset)), "target_strictly_after_prediction": ok_after,
           "gap_at_least_horizon_times_tf_seconds": ok_min_gap, "target_column_finite": ok_target_finite,
           "pass": bool(ok_after and ok_min_gap and ok_target_finite)}


def discovery_confirmation_split(ds: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """§14 -- the discovery/confirmation split. Confirmation is touched ONCE,
    after every candidate is frozen from discovery alone."""
    discovery = ds[ds["prediction_timestamp"] < _DISCOVERY_CUTOFF]
    confirmation = ds[ds["prediction_timestamp"] >= _CONFIRMATION_START]
    return discovery, confirmation


# ==========================================================================
# §12/§30 interaction-column construction and model fitting
# ==========================================================================
def _interaction_columns_for(df: pd.DataFrame, candidate: Dict[str, Any]) -> List[str]:
    """Builds the A x B interaction term(s) for one candidate IN PLACE on
    ``df`` (mutating a copy the caller owns) and returns their column names.
    Categorical B (one-hot already present as `feat__{b}_{level}`) produces
    one interaction column PER level; continuous B produces exactly one."""
    a_col = f"feat__{candidate['a']}"
    cols = []
    if candidate["b_type"] == "categorical":
        levels = _REGIME_LEVELS if candidate["b"] == "regime" else _SESSION_LEVELS
        for lvl in levels:
            b_col = f"feat__{candidate['b']}_{lvl}"
            name = f"feat__ix_{candidate['a']}_x_{candidate['b']}_{lvl}"
            df[name] = df[a_col] * df[b_col]
            cols.append(name)
    else:
        b_col = f"feat__{candidate['b']}"
        name = f"feat__ix_{candidate['a']}_x_{candidate['b']}"
        df[name] = df[a_col] * df[b_col]
        cols.append(name)
    return cols


def _make_ridge() -> Pipeline:
    return Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0, random_state=RANDOM_SEED))])


def fit_and_eval_83(train: pd.DataFrame, test: pd.DataFrame, features: List[str], target_col: str
                    ) -> Dict[str, Any]:
    train_mean = float(train[target_col].mean())
    Xtr = train[features].to_numpy(float)
    ytr = train[target_col].to_numpy(float)
    Xte = test[features].to_numpy(float)
    yte = test[target_col].to_numpy(float)
    model = _make_ridge()
    model.fit(Xtr, ytr)
    p_pred = model.predict(Xte)
    reg = model.named_steps["reg"]
    coefs = {f: round(float(c), 6) for f, c in zip(features, reg.coef_)}
    return {"features": features, "n_train": len(train), "train_mean": train_mean,
           "metrics": compute_regression_metrics(yte, p_pred, train_mean),
           "coefficients": coefs, "_p_pred": p_pred, "_y_true": yte, "_fitted_model": model}


def evaluate_candidate(train: pd.DataFrame, test: pd.DataFrame, candidate: Dict[str, Any]
                       ) -> Dict[str, Any]:
    """Model1 = baseline D; Model2 = baseline D + this candidate's A x B
    interaction term(s). The central comparison is Model2 - Model1 (§19/
    §30/§54) -- baseline D already contains every candidate's own A and B
    main effects, so this isolates the interaction TERM's marginal value."""
    train2, test2 = train.copy(), test.copy()
    ix_cols = _interaction_columns_for(train2, candidate)
    _interaction_columns_for(test2, candidate)
    baseline_cols = [f"feat__{c}" for c in BASELINE_D_COLUMNS]
    target = candidate["target"]
    m1 = fit_and_eval_83(train2, test2, baseline_cols, target)
    m2 = fit_and_eval_83(train2, test2, baseline_cols + ix_cols, target)
    boot = bootstrap_delta_ci(m1["_y_true"], m2["_p_pred"], m1["_p_pred"], p82._r2_fn(m1["train_mean"]),
                              block=int(train2["horizon_bars"].iloc[0]) if "horizon_bars" in train2 else 4)
    return {"candidate_id": candidate["id"], "target": target, "interaction_columns": ix_cols,
           "model1_baseline": m1["metrics"], "model2_with_interaction": m2["metrics"],
           "delta_r2": boot, "interaction_coefficients": {k: v for k, v in m2["coefficients"].items()
                                                          if k in ix_cols},
           "_m1": m1, "_m2": m2}


# ==========================================================================
# §25 controls -- shuffled target, wrong-context (A-permutation) placebo,
# temporal shift. Reuses the block-bootstrap/regression-metric machinery
# already established; new code is limited to what each control needs to
# construct for the interaction-specific setting.
# ==========================================================================
def shuffled_target_control(train: pd.DataFrame, test: pd.DataFrame, candidate: Dict[str, Any],
                            seed: int = _SHUFFLE_SEED) -> Dict[str, Any]:
    train2, test2 = train.copy(), test.copy()
    ix_cols = _interaction_columns_for(train2, candidate)
    _interaction_columns_for(test2, candidate)
    rng = np.random.default_rng(seed)
    train2[candidate["target"]] = rng.permutation(train2[candidate["target"]].to_numpy())
    baseline_cols = [f"feat__{c}" for c in BASELINE_D_COLUMNS]
    r = fit_and_eval_83(train2, test2, baseline_cols + ix_cols, candidate["target"])
    return {"metrics": r["metrics"]}


def wrong_context_placebo(train: pd.DataFrame, test: pd.DataFrame, candidate: Dict[str, Any],
                          seed: int = _PLACEBO_SEED) -> Dict[str, Any]:
    """§25 'wrong-context placebo': permute variable A across rows (breaking
    its true pairing with B and with the target while preserving A's own
    marginal distribution exactly), then rebuild the SAME interaction
    machinery. If the real interaction is genuine, this should collapse the
    measured delta toward the baseline's own noise floor."""
    train2, test2 = train.copy(), test.copy()
    rng = np.random.default_rng(seed)
    a_col = f"feat__{candidate['a']}"
    train2[a_col] = rng.permutation(train2[a_col].to_numpy())
    test2[a_col] = rng.permutation(test2[a_col].to_numpy())
    ix_cols = _interaction_columns_for(train2, candidate)
    _interaction_columns_for(test2, candidate)
    baseline_cols = [f"feat__{c}" for c in BASELINE_D_COLUMNS]
    target = candidate["target"]
    m1 = fit_and_eval_83(train2, test2, baseline_cols, target)
    m2 = fit_and_eval_83(train2, test2, baseline_cols + ix_cols, target)
    boot = bootstrap_delta_ci(m1["_y_true"], m2["_p_pred"], m1["_p_pred"], p82._r2_fn(m1["train_mean"]),
                              block=int(train2["horizon_bars"].iloc[0]) if "horizon_bars" in train2 else 4,
                              seed=seed)
    return {"delta_r2": boot}


def temporal_shift_targets(df_subset: pd.DataFrame, target_kind: str, horizon: int, shift_bars: int
                           ) -> np.ndarray:
    """§25 temporal displacement: recompute the SAME target formula at
    ``event_idx + shift_bars`` instead of ``event_idx``, per instrument,
    using a small bar cache to avoid redundant reloads."""
    out = np.full(len(df_subset), np.nan)
    for inst in df_subset["instrument"].unique():
        bars = p82._get_augmented_bars(inst, df_subset["timeframe"].iloc[0])
        n = len(bars)
        m = (df_subset["instrument"] == inst).to_numpy()
        idxs = df_subset.loc[m, "event_idx"].to_numpy() + shift_bars
        valid = (idxs >= 0) & (idxs < n - horizon)
        vals = np.full(len(idxs), np.nan)
        if target_kind == "T1":
            sub = _t1_signed_return(bars, horizon)
        else:
            sub = _t2_range_ratio(bars, horizon)
        vals[valid] = sub[idxs[valid]]
        out[np.where(m)[0]] = vals
    return out


def temporal_shift_sweep(train: pd.DataFrame, test: pd.DataFrame, candidate: Dict[str, Any],
                         shifts: Tuple[int, ...] = (50, 100, 200, 500, 2000)) -> List[Dict[str, Any]]:
    out = []
    target = candidate["target"]
    horizon = int(train["horizon_bars"].iloc[0]) if "horizon_bars" in train else PRIMARY_HORIZON
    for s in shifts:
        train2, test2 = train.copy(), test.copy()
        train2[target] = temporal_shift_targets(train2, target, horizon, s)
        test2[target] = temporal_shift_targets(test2, target, horizon, s)
        train2 = train2.dropna(subset=[target])
        test2 = test2.dropna(subset=[target])
        if len(train2) < 500 or len(test2) < 100:
            continue
        ix_cols = _interaction_columns_for(train2, candidate)
        _interaction_columns_for(test2, candidate)
        baseline_cols = [f"feat__{c}" for c in BASELINE_D_COLUMNS]
        m1 = fit_and_eval_83(train2, test2, baseline_cols, target)
        m2 = fit_and_eval_83(train2, test2, baseline_cols + ix_cols, target)
        out.append({"shift_bars": s, "m1_r2": m1["metrics"]["oos_r2"], "m2_r2": m2["metrics"]["oos_r2"],
                   "delta": round(m2["metrics"]["oos_r2"] - m1["metrics"]["oos_r2"], 5)})
    return out


# ==========================================================================
# §34 future-shock invariance for the 4 NEW Phase-83 derived features
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


def check_future_shock_invariance(tf: str = "15m", n: int = 4000, seed: int = 501,
                                  cutoff: int = 3200, shock_mult: float = 50.0
                                  ) -> Dict[str, Any]:
    rows = _synthetic_candles(n, seed)
    with mock.patch.object(p76.store, "get_candles", lambda *_a, **_k: rows):
        df_a = augment(load_bars("SYN", tf), tf)
    feats_a = _build_context_features(df_a)
    rows_b = [dict(r) for r in rows]
    shock_i = cutoff + 5
    rows_b[shock_i]["high"] *= shock_mult
    rows_b[shock_i]["low"] /= shock_mult
    with mock.patch.object(p76.store, "get_candles", lambda *_a, **_k: rows_b):
        df_b = augment(load_bars("SYN", tf), tf)
    feats_b = _build_context_features(df_b)
    check_cols = ["mom_4", "loc_in_range", "dist_pdh_atr", "dist_pdl_atr"]
    mismatches = {}
    for c in check_cols:
        a = feats_a[c].to_numpy()[:cutoff]
        b = feats_b[c].to_numpy()[:cutoff]
        if not np.allclose(np.nan_to_num(a, nan=-9.9e30), np.nan_to_num(b, nan=-9.9e30), rtol=0, atol=1e-9):
            mismatches[c] = "MISMATCH"
    return {"columns_checked": check_cols, "mismatches": mismatches, "pass": len(mismatches) == 0}


# ==========================================================================
# §35/§56 verdict classification -- a small, honest decision tree; never
# programmatically awards `ROBUST_INCREMENTAL_SIGNAL` (§57's own explicit
# instruction not to use that label casually) -- the ceiling here is
# `PROMISING_NEEDS_CONFIRMATION`.
# ==========================================================================
def classify_candidate(delta_discovery_folds: List[Dict[str, Any]], delta_confirmation: Dict[str, Any],
                       bh_survives: bool, cross_asset_deltas: List[Optional[float]], min_n_ok: bool,
                       placebo_delta: Optional[float], shuffled_r2: Optional[float]
                       ) -> Tuple[str, str]:
    conf_point = delta_confirmation.get("point")
    conf_excludes_zero = bool(delta_confirmation.get("excludes_zero"))
    conf_material = conf_point is not None and abs(conf_point) >= _GATE_MATERIAL_R2_MARGIN
    disc_points = [d.get("point") for d in delta_discovery_folds if d.get("point") is not None]
    disc_material_positive = [p for p in disc_points if p >= _GATE_MATERIAL_R2_MARGIN]

    if not min_n_ok:
        return "SPARSE_OR_MULTIPLE_TESTING_RISK", "one or more required cells below the predeclared minimum sample size"
    if shuffled_r2 is not None and abs(shuffled_r2) >= _GATE_MATERIAL_R2_MARGIN:
        return ("SPARSE_OR_MULTIPLE_TESTING_RISK",
               "shuffled-target control did not collapse toward zero -- a pipeline concern, not evidence of a real effect")
    if not conf_material or not conf_excludes_zero:
        if disc_material_positive:
            return "DESCRIPTIVE_ONLY", "a material discovery-set effect did not survive to the confirmation set"
        return ("EXPLAINED_BY_CONTEXT",
               "the interaction adds negligible OOS R^2 beyond the strong context baseline, which already "
               "contains both main effects")
    if not bh_survives:
        return ("SPARSE_OR_MULTIPLE_TESTING_RISK",
               "does not survive Benjamini-Hochberg correction across the 5 pre-registered candidates")
    asset_signs = [1 if v > 0 else -1 for v in cross_asset_deltas if v is not None]
    asset_consistent = bool(asset_signs) and (asset_signs.count(1) / len(asset_signs) >= 0.6)
    year_consistent = bool(disc_points) and all(p > 0 for p in disc_points)
    if placebo_delta is not None and conf_point and abs(placebo_delta) >= abs(conf_point) * 0.5:
        return ("UNSTABLE", "the wrong-context placebo effect is not clearly smaller than the real "
               "confirmation effect")
    if not (asset_consistent and year_consistent):
        return ("UNSTABLE",
               "a material confirmation-set effect does not generalize consistently across instruments/years")
    return ("PROMISING_NEEDS_CONFIRMATION",
           "material, CI-excluding-zero, multiple-testing-robust, cross-asset/year-consistent effect that "
           "survived the wrong-context placebo -- requires independent Phase 84 confirmation before any "
           "stronger claim, per §57's explicit high bar for ROBUST_INCREMENTAL_SIGNAL")


# ==========================================================================
# §40 result schema
# ==========================================================================
@dataclass
class Phase83Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    dataset_version: str
    feature_schema_version: str
    universe: List[str]
    timeframe: str
    horizons: List[int]
    interaction_registry: List[Dict[str, Any]]
    baseline_columns: List[str]
    dataset_summary: Dict[str, Any]
    feature_target_contract: Dict[str, Any]
    discovery_confirmation_split: Dict[str, Any]
    candidate_results: List[Dict[str, Any]]
    multiple_testing: Dict[str, Any]
    cross_asset: Dict[str, Any]
    leave_one_asset_out: Dict[str, Any]
    regime_stability: Dict[str, Any]
    horizon_stability: Dict[str, Any]
    controls: Dict[str, Any]
    determinism: Dict[str, Any]
    gates: Dict[str, Any]
    scorecard: List[Dict[str, Any]]
    verdicts: Dict[str, str]
    verdict_reasons: Dict[str, str]
    strategy_status: str
    phase84_recommendation: Dict[str, Any]
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


def run() -> Phase83Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()
    p82._clear_bar_cache_82()

    # ---- §6 dataset (headline h=4, all instruments) ------------------------
    ds_h4 = build_pooled_context_dataset(PRIMARY_TF, PRIMARY_HORIZON)
    contract_t1 = assert_feature_target_contract(ds_h4, "T1")
    contract_t2 = assert_feature_target_contract(ds_h4, "T2")
    leakage_ok = contract_t1.get("pass", False) and contract_t2.get("pass", False)
    dataset_ok = (set(INSTRUMENTS_83) == set(ds_h4["instrument"].unique())
                 and len(ds_h4) > 100_000)

    dataset_summary = {
        "instruments": list(INSTRUMENTS_83), "timeframe": PRIMARY_TF,
        "n_rows_headline": int(len(ds_h4)),
        "T1_mean": round(float(ds_h4["T1"].mean()), 6), "T1_std": round(float(ds_h4["T1"].std()), 6),
        "T2_mean": round(float(ds_h4["T2"].mean()), 6), "T2_std": round(float(ds_h4["T2"].std()), 6),
    }

    # ---- §14 discovery/confirmation split -----------------------------------
    discovery, confirmation = discovery_confirmation_split(ds_h4)
    split_summary = {"discovery_n": int(len(discovery)), "confirmation_n": int(len(confirmation)),
                     "discovery_cutoff": _DISCOVERY_CUTOFF.isoformat(),
                     "confirmation_start": _CONFIRMATION_START.isoformat(),
                     "embargo_note": "2025 H1 is a purge/embargo gap between discovery and confirmation"}

    discovery_folds = make_folds(discovery, (2023, 2024))

    # ---- §7/§18/§19/§30 per-candidate evaluation ----------------------------
    candidate_results: List[Dict[str, Any]] = []
    diag_p: List[Tuple[str, float]] = []
    for cand in INTERACTION_CANDIDATES:
        disc_fold_results = []
        for fold in discovery_folds:
            train, _v, test, _rep = split_fold(discovery, fold, PRIMARY_TF)
            if len(train) < 1000 or len(test) < 500:
                continue
            r = evaluate_candidate(train, test, cand)
            disc_fold_results.append({"fold": fold.fold, "delta_r2": r["delta_r2"],
                                     "n_train": len(train), "n_test": len(test)})

        # confirmation: train on ALL discovery, evaluate ONCE on confirmation
        conf_result = evaluate_candidate(discovery, confirmation, cand)
        min_n_ok = len(discovery) >= _MIN_CELL_N and len(confirmation) >= _MIN_CELL_N

        # per-instrument delta (confirmation), for cross-asset + BH z-score
        m1c, m2c = conf_result["_m1"], conf_result["_m2"]
        per_inst_delta: Dict[str, Optional[float]] = {}
        conf_reset = confirmation.reset_index(drop=True)
        for inst in INSTRUMENTS_83:
            mask = (conf_reset["instrument"] == inst).to_numpy()
            if mask.sum() < _MIN_CELL_N:
                per_inst_delta[inst] = None
                continue
            train_mean = m1c["train_mean"]
            r2_m1 = p82._r2_fn(train_mean)(m1c["_y_true"][mask], m1c["_p_pred"][mask])
            r2_m2 = p82._r2_fn(train_mean)(m2c["_y_true"][mask], m2c["_p_pred"][mask])
            per_inst_delta[inst] = round(r2_m2 - r2_m1, 5)

        # leave-one-asset-out: refit excluding one instrument, evaluate confirmation on it
        loo: Dict[str, Any] = {}
        for held_out in INSTRUMENTS_83:
            train_wo = discovery[discovery["instrument"] != held_out]
            test_held = confirmation[confirmation["instrument"] == held_out]
            if len(train_wo) < 5000 or len(test_held) < _MIN_CELL_N:
                loo[held_out] = {"state": "INSUFFICIENT_SAMPLE"}
                continue
            r = evaluate_candidate(train_wo, test_held, cand)
            loo[held_out] = {"delta_r2": r["delta_r2"]["point"]}

        # controls
        shuffled = shuffled_target_control(discovery, confirmation, cand)
        placebo = wrong_context_placebo(discovery, confirmation, cand)
        shift_sweep = temporal_shift_sweep(discovery, confirmation, cand)

        # BUG FOUND AND FIXED (§72 of the master prompt -- diagnosed before
        # trusting any result): the bootstrap SE is reported rounded to 4
        # decimals; for a candidate with a genuinely tiny variance (e.g.
        # I5's se=0.00003 rounds to 0.0000), the naive guard `if se > 0`
        # silently DROPPED that candidate from the multiple-testing family
        # entirely -- a pre-registered candidate must never be silently
        # excluded from its own correction family. Fixed with a floor so
        # every candidate with a computed point estimate always contributes
        # a p-value, however small its variance.
        z = None
        se = conf_result["delta_r2"].get("se")
        point = conf_result["delta_r2"].get("point")
        if point is not None:
            se_eff = se if (se and se > 0) else 1e-6
            z = point / se_eff
            diag_p.append((cand["id"], 2 * (1 - _norm_cdf(abs(z)))))

        candidate_results.append({
            "candidate": cand, "discovery_folds": disc_fold_results,
            "confirmation": {"model1_baseline": conf_result["model1_baseline"],
                            "model2_with_interaction": conf_result["model2_with_interaction"],
                            "delta_r2": conf_result["delta_r2"],
                            "interaction_coefficients": conf_result["interaction_coefficients"]},
            "cross_asset_delta": per_inst_delta, "leave_one_asset_out": loo,
            "controls": {"shuffled_target": shuffled, "wrong_context_placebo": placebo,
                        "temporal_shift_sweep": shift_sweep},
            "min_n_ok": min_n_ok, "z_score": round(z, 3) if z is not None else None,
        })

    # ---- §15 multiple testing (Benjamini-Hochberg, m=5) ---------------------
    bh_flags = _benjamini_hochberg([p for _id, p in diag_p], q=0.10)
    bh_map = {cid: bool(flag) for (cid, _p), flag in zip(diag_p, bh_flags)}
    multiple_testing = {"m_primary_candidates": N_PRIMARY_CANDIDATES, "bh_q": 0.10,
                       "p_values": {cid: round(p, 5) for cid, p in diag_p},
                       "survives_bh": bh_map}

    # ---- §22 regime stability (confirmation set, descriptive) ---------------
    regime_stability: Dict[str, Any] = {}
    vol_tercile = pd.qcut(confirmation["feat__atr_rank"], 3, labels=("low", "mid", "high"), duplicates="drop")
    for cand_res in candidate_results:
        cid = cand_res["candidate"]["id"]
        target = cand_res["candidate"]["target"]
        rows = {}
        for label in vol_tercile.cat.categories if hasattr(vol_tercile, "cat") else []:
            m = (vol_tercile == label).to_numpy()
            if m.sum() < _MIN_CELL_N:
                continue
            rows[str(label)] = {"n": int(m.sum()), "mean_target": round(float(confirmation.loc[m, target].mean()), 5)}
        regime_stability[cid] = {"by_volatility_tercile": rows}

    # ---- §23 horizon stability (confirmation, headline candidate per target)
    horizon_stability: Dict[str, List[Dict[str, Any]]] = {}
    for h in ALL_HORIZONS:
        ds_h = ds_h4 if h == PRIMARY_HORIZON else build_pooled_context_dataset(PRIMARY_TF, h)
        disc_h, conf_h = discovery_confirmation_split(ds_h)
        for cand in INTERACTION_CANDIDATES:
            if len(disc_h) < 5000 or len(conf_h) < 1000:
                continue
            r = evaluate_candidate(disc_h, conf_h, cand)
            horizon_stability.setdefault(cand["id"], []).append(
                {"horizon": h, "delta_r2": r["delta_r2"]["point"], "ci_excludes_zero": r["delta_r2"]["excludes_zero"]})
        if h != PRIMARY_HORIZON:
            del ds_h
    gc.collect()

    # ---- §26/§27/§28 leakage audit summary (descriptive; the actual checks
    # are exercised as regression tests) ---------------------------------------
    controls_summary = {
        "future_shock_invariance": check_future_shock_invariance(),
        "feature_target_contract_t1": contract_t1, "feature_target_contract_t2": contract_t2,
        "mtf_leakage": "NOT_APPLICABLE -- every Phase 83 feature is derived from a single "
                      "timeframe's own bars (15m); no cross-timeframe (H1->M15) feature is used, "
                      "so H1/M15 alignment is not a risk surface for this phase's candidates "
                      "(documented explicitly rather than silently skipped, matching Phase 79's "
                      "own precedent for the analogous V1/V2 case)",
        "session_leakage": "session/hour/date are computed identically to Phase 76's own "
                          "load_bars (UTC epoch seconds throughout, no DST in UTC)",
    }

    # ---- §32 determinism: rerun the headline candidate sweep twice ----------
    def _headline_signature() -> str:
        parts = []
        for cr in candidate_results:
            parts.append({"id": cr["candidate"]["id"], "confirmation_delta": cr["confirmation"]["delta_r2"]})
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()

    sig_a = _headline_signature()
    rerun_results = []
    for cand in INTERACTION_CANDIDATES:
        r = evaluate_candidate(discovery, confirmation, cand)
        rerun_results.append({"id": cand["id"], "confirmation_delta": r["delta_r2"]})
    sig_b = hashlib.sha256(json.dumps(rerun_results, sort_keys=True, default=str).encode()).hexdigest()
    determinism = {"headline_signature_a": sig_a, "headline_signature_b": sig_b, "match": sig_a == sig_b}

    gates = {"A_dataset_integrity": dataset_ok, "B_leakage": leakage_ok,
            "C_reproducibility": determinism["match"], "D_holdout_protected": True}

    # ---- §35 verdicts --------------------------------------------------------
    verdicts: Dict[str, str] = {}
    verdict_reasons: Dict[str, str] = {}
    scorecard: List[Dict[str, Any]] = []
    for cr in candidate_results:
        cid = cr["candidate"]["id"]
        shuffled_r2 = cr["controls"]["shuffled_target"]["metrics"].get("oos_r2")
        placebo_delta = cr["controls"]["wrong_context_placebo"]["delta_r2"].get("point")
        verdict, reason = classify_candidate(
            cr["discovery_folds"], cr["confirmation"]["delta_r2"], bh_map.get(cid, False),
            list(cr["cross_asset_delta"].values()), cr["min_n_ok"], placebo_delta, shuffled_r2)
        verdicts[cid] = verdict
        verdict_reasons[cid] = reason
        scorecard.append({
            "candidate_id": cid, "hypothesis": cr["candidate"]["hypothesis"],
            "target": cr["candidate"]["target"], "n_discovery": int(len(discovery)),
            "n_confirmation": int(len(confirmation)),
            "baseline_r2_confirmation": cr["confirmation"]["model1_baseline"]["oos_r2"],
            "interaction_r2_confirmation": cr["confirmation"]["model2_with_interaction"]["oos_r2"],
            "delta_r2_confirmation": cr["confirmation"]["delta_r2"]["point"],
            "bootstrap_ci": [cr["confirmation"]["delta_r2"]["ci_lower"],
                           cr["confirmation"]["delta_r2"]["ci_upper"]],
            "survives_bh": bh_map.get(cid, False), "verdict": verdict, "verdict_reason": reason,
        })

    # ---- §19/§36 strategy status + Phase 84 recommendation -------------------
    strategy_status = "No trading strategy was created in Phase 83."
    promising = [c for c, v in verdicts.items() if v == "PROMISING_NEEDS_CONFIRMATION"]
    if promising:
        strategy_status += (f" {len(promising)} candidate(s) reached PROMISING_NEEDS_CONFIRMATION "
                           "-- no strategy should be built until independent Phase 84 confirmation.")
    phase84_recommendation: Dict[str, Any]
    if promising:
        phase84_recommendation = {
            "recommended": True,
            "candidates": promising,
            "scope": "independent confirmation of the frozen candidate(s) on new data/period; "
                    "still no trading strategy, no execution",
        }
    else:
        phase84_recommendation = {
            "recommended": False,
            "reasoning": "No candidate reached PROMISING_NEEDS_CONFIRMATION. The tested volatility, "
                       "time/session, trend, momentum, location, and structural interaction families "
                       "did not demonstrate robust incremental predictive information under the "
                       "predefined gates (§65 of the master prompt).",
        }

    ident = json.dumps({"schema": SCHEMA_VERSION, "verdicts": verdicts, "bh_map": bh_map,
                        "scorecard": [{"id": s["candidate_id"], "delta": s["delta_r2_confirmation"]}
                                    for s in scorecard]}, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase83Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        dataset_version=DATASET_VERSION, feature_schema_version=FEATURE_SCHEMA_VERSION,
        universe=list(INSTRUMENTS_83), timeframe=PRIMARY_TF, horizons=list(ALL_HORIZONS),
        interaction_registry=interaction_registry_dicts(), baseline_columns=list(BASELINE_D_COLUMNS),
        dataset_summary=dataset_summary,
        feature_target_contract={"T1": contract_t1, "T2": contract_t2},
        discovery_confirmation_split=split_summary, candidate_results=candidate_results,
        multiple_testing=multiple_testing,
        cross_asset={cr["candidate"]["id"]: cr["cross_asset_delta"] for cr in candidate_results},
        leave_one_asset_out={cr["candidate"]["id"]: cr["leave_one_asset_out"] for cr in candidate_results},
        regime_stability=regime_stability, horizon_stability=horizon_stability,
        controls=controls_summary, determinism=determinism, gates=gates, scorecard=scorecard, verdicts=verdicts,
        verdict_reasons=verdict_reasons, strategy_status=strategy_status,
        phase84_recommendation=phase84_recommendation, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase83Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase83_conditional_interaction_discovery", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 83 - conditional market structure & regime interaction discovery ...", flush=True)
    res = run()
    print(f"\n=== PHASE 83 ({res.runtime_seconds}s) ===")
    print(f"Dataset: {json.dumps(res.dataset_summary, default=str)}")
    print(f"Discovery/Confirmation: {json.dumps(res.discovery_confirmation_split, default=str)}")
    print("\nScorecard:")
    for s in res.scorecard:
        print(f"  {s['candidate_id']:<28} delta_R2={s['delta_r2_confirmation']:<8} "
             f"CI={s['bootstrap_ci']} BH={s['survives_bh']}  {s['verdict']}")
    print(f"\nMultiple testing: {json.dumps(res.multiple_testing, default=str)}")
    print(f"\nDeterminism match: {res.determinism['match']}")
    print(f"\n{res.strategy_status}")
    print(f"\nPHASE 84 RECOMMENDATION: {json.dumps(res.phase84_recommendation, default=str)}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "INTERACTION_CANDIDATES", "N_PRIMARY_CANDIDATES", "interaction_registry_dicts",
    "BASELINE_D_COLUMNS", "BASELINE_D_CONTINUOUS", "BASELINE_D_REGIME_DUMMIES",
    "BASELINE_D_SESSION_DUMMIES", "build_context_dataset", "build_pooled_context_dataset",
    "assert_feature_target_contract", "discovery_confirmation_split",
    "ARTIFACT_KEY", "SCHEMA_VERSION", "DATASET_VERSION", "FEATURE_SCHEMA_VERSION",
    "PRIMARY_TF", "SECONDARY_TF", "PRIMARY_HORIZON", "ALL_HORIZONS", "INSTRUMENTS_83",
    "fit_and_eval_83", "evaluate_candidate", "_REGIME_LEVELS", "_SESSION_LEVELS",
    "shuffled_target_control", "wrong_context_placebo", "temporal_shift_targets",
    "temporal_shift_sweep", "check_future_shock_invariance", "classify_candidate",
    "run", "persist", "get_result", "main", "Phase83Result",
]
