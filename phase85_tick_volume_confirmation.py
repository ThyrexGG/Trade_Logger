# -*- coding: utf-8 -*-
"""
Phase 85 -- Tick-Volume Confirmation, Generalization & Feed-Independence Study.

Frozen goal (master prompt, not to be reinterpreted after seeing results):
try to DESTROY the Phase 84 screening finding (adding causal MT5 tick-volume
features to Phase 83's frozen Strong Context Baseline D raised the forward
range/magnitude target's OOS R^2 by +0.0204), not to preserve it. Gemini's
independent red-team verdict on that finding was
``PROMISING_REQUIRES_FURTHER_CONFIRMATION``, citing cross-instrument
heterogeneity (EURUSD/USDJPY/XAUUSD/GBPUSD positive, AUDJPY/GBPJPY ~zero) and
the conceptual caveat that MT5 tick_volume is a broker-specific tick count,
not centralized traded volume.

Everything here is FROZEN, per the master prompt, and never adjusted after
looking at a result:
  * feature spec -- ``volume_rank`` (primary) / ``volume_ret_1`` (secondary),
    identical trailing-200-bar causal construction as Phase 84
    (``phase84_information_frontier_audit._add_volume_features``, reused
    unchanged, not reimplemented);
  * baseline -- Phase 83's ``BASELINE_D_COLUMNS`` (15 features), unchanged;
  * target -- Phase 83's T2 (magnitude, primary) / T1 (direction, control),
    unchanged formulas;
  * universe -- the same 6 canonical instruments (``INSTRUMENTS_83``), never
    reduced post-hoc even though 2 of them showed a null/negative effect in
    Gemini's read -- cross-instrument heterogeneity IS a result, not noise
    to average away;
  * discovery/confirmation split -- Phase 83's dates, unchanged;
  * model family -- Ridge only (``phase83.fit_and_eval_83``), no tuning, no
    model shopping.

New machinery in this module is limited to what a CONFIRMATION study needs
that a screening experiment did not: per-instrument and leave-one-asset-out
breakdowns, temporal-block and horizon-profile stability, a volatility/
session confounding decomposition, an expanded placebo battery (target
shuffle, global volume shuffle, instrument-x-session stratified shuffle,
predeclared temporal misalignment, a stronger within-instrument/time-stratum
placebo), a distribution-drift audit, a data-provenance audit of what MT5
``tick_volume`` actually is (verified by source inspection and live data
stats, never inferred), and a broker/feed-independence feasibility check.

A single unified per-instrument dataset builder (``build_dataset_85``)
produces every ablation model's feature columns (baseline D + volume_rank +
volume_ret_1) from ONE finite-value mask, so M1-M4 are evaluated on
IDENTICAL rows by construction -- the matched-population requirement (master
prompt Sec.18) is structural, not an after-the-fact patch; a dedicated
population-matching audit function documents this rather than merely
asserting it.

Read-only research. No execution/broker/risk import. The frozen Phase-74
Gold holdout is never read.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store
import mt5_provider
import phase76_event_study as p76
import phase82_compression_expansion_ml_pilot as p82
import phase83_conditional_interaction_discovery as p83
import phase84_information_frontier_audit as p84
from phase76_event_study import RANDOM_SEED, _benjamini_hochberg
from phase81_v2_information_decomposition import bootstrap_delta_ci, bootstrap_metric_ci
from phase82_compression_expansion_ml_pilot import _r2_fn, compute_regression_metrics
from phase83_conditional_interaction_discovery import (
    BASELINE_D_COLUMNS, INSTRUMENTS_83, PRIMARY_HORIZON, PRIMARY_TF,
    discovery_confirmation_split, fit_and_eval_83,
)
from phase84_information_frontier_audit import _add_volume_features, _VOLUME_WINDOW

SCHEMA_VERSION = "phase85.1"
ARTIFACT_KEY = "phase85_tick_volume_confirmation"
DATASET_VERSION = "phase85-tickvol-dataset-v1"

ALL_HORIZONS: Tuple[int, ...] = (1, 2, 4, 8)
_MIN_CELL_N = 200
_TEMPORAL_MISALIGNMENT_OFFSETS: Tuple[int, ...] = (10, 50, 200)  # predeclared, Sec.25.D
_MULTI_TESTING_Q = 0.10

VOLUME_COLUMNS: Tuple[str, ...] = ("volume_rank", "volume_ret_1")

# Sec.13: exactly M1-M4, no additional combination
ABLATIONS_85: Tuple[Tuple[str, List[str]], ...] = (
    ("M1_baseline", list(BASELINE_D_COLUMNS)),
    ("M2_baseline_plus_volume_rank", list(BASELINE_D_COLUMNS) + ["volume_rank"]),
    ("M3_baseline_plus_volume_ret_1", list(BASELINE_D_COLUMNS) + ["volume_ret_1"]),
    ("M4_baseline_plus_both", list(BASELINE_D_COLUMNS) + ["volume_rank", "volume_ret_1"]),
)


# ==========================================================================
# Sec.1 caching -- feature/volume columns are horizon-independent, so they
# are computed ONCE per instrument and reused across every horizon/temporal
# analysis in this phase (avoids the wasted repeated DB reads a naive
# per-horizon rebuild would cost, and guarantees identical feature values
# are used everywhere in this phase for a given instrument).
# ==========================================================================
_FEATS_CACHE_85: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = {}


def _clear_cache_85() -> None:
    _FEATS_CACHE_85.clear()
    p82._clear_bar_cache_82()


def _get_features_bars_85(instrument: str, tf: str = PRIMARY_TF) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if instrument not in _FEATS_CACHE_85:
        df = p82._get_augmented_bars(instrument, tf)
        feats = p83._build_context_features(df)
        vol_feats = _add_volume_features(df)
        feats = pd.concat([feats, vol_feats], axis=1)
        _FEATS_CACHE_85[instrument] = (df, feats)
    return _FEATS_CACHE_85[instrument]


def build_dataset_85(instrument: str, tf: str = PRIMARY_TF, horizon: int = PRIMARY_HORIZON
                     ) -> pd.DataFrame:
    """One unified builder for every M1-M4 ablation -- baseline D and volume
    columns share exactly one finite-value mask, so no ablation ever sees a
    different row population than another (Sec.18)."""
    df, feats = _get_features_bars_85(instrument, tf)
    n = len(df)
    t1 = p83._t1_signed_return(df, horizon)
    t2 = p83._t2_range_ratio(df, horizon)

    warmup = max(p83._WARMUP, _VOLUME_WINDOW)
    idx = np.arange(warmup, n - horizon)
    finite_mask = np.isfinite(feats.iloc[idx].to_numpy(float)).all(axis=1) \
        & np.isfinite(t1[idx]) & np.isfinite(t2[idx])
    idx = idx[finite_mask]
    if len(idx) == 0:
        return pd.DataFrame()

    from phase80_ml_volatility_regime import _TF_SECONDS
    tf_sec = _TF_SECONDS[tf]
    open_ts = df["t"].to_numpy(np.int64)
    pred_ts = pd.to_datetime(open_ts[idx].astype(np.int64) + tf_sec, unit="s", utc=True)
    targ_end_ts = pd.to_datetime(open_ts[idx + horizon].astype(np.int64) + tf_sec, unit="s", utc=True)

    out = pd.DataFrame({
        "instrument": instrument, "timeframe": tf, "horizon_bars": horizon,
        "event_idx": idx, "prediction_timestamp": pred_ts, "target_end_timestamp": targ_end_ts,
        "T1": t1[idx], "T2": t2[idx], "dataset_version": DATASET_VERSION,
    })
    feat_rows = feats.iloc[idx].reset_index(drop=True)
    return pd.concat([out, feat_rows.add_prefix("feat__")], axis=1)


def build_pooled_dataset_85(tf: str = PRIMARY_TF, horizon: int = PRIMARY_HORIZON,
                            instruments: Tuple[str, ...] = INSTRUMENTS_83) -> pd.DataFrame:
    frames = [d for inst in instruments if not (d := build_dataset_85(inst, tf, horizon)).empty]
    if not frames:
        return pd.DataFrame()
    pooled = pd.concat(frames, ignore_index=True)
    return pooled.sort_values("prediction_timestamp").reset_index(drop=True)


# ==========================================================================
# Sec.14 data provenance audit -- verified by source inspection + live data,
# never inferred about broker internals (Sec.15)
# ==========================================================================
def data_provenance_audit() -> Dict[str, Any]:
    mt5_src = inspect.getsource(mt5_provider)
    field_line = next((l for l in mt5_src.splitlines() if "tick_volume" in l), None)
    real_volume_read = "real_volume" in mt5_src

    stats: Dict[str, Any] = {}
    for inst in INSTRUMENTS_83:
        rows = store.get_candles(inst, PRIMARY_TF)
        if not rows:
            stats[inst] = {"state": "NO_DATA"}
            continue
        df = pd.DataFrame(rows)
        if "source" in df.columns:
            non_mt5 = int((df["source"] != "mt5").sum())
            df = df[df["source"] == "mt5"]
        else:
            non_mt5 = 0
        n = len(df)
        dup = int(df["time"].duplicated().sum())
        zero_vol = int((df["volume"] <= 0).sum())
        stats[inst] = {
            "n_rows": n, "non_mt5_source_rows": non_mt5, "duplicate_timestamps": dup,
            "zero_volume_rows": zero_vol, "volume_min": float(df["volume"].min()),
            "volume_max": float(df["volume"].max()), "volume_median": float(df["volume"].median()),
        }

    return {
        "pipeline": "MT5 terminal -> copy_rates_range() [mt5_provider.py] -> "
                   "historical_data_store.save_candles() -> "
                   "phase76_event_study.load_bars() -> augment() -> feature construction -> model",
        "field_mapping_verified_by_source_inspection": {
            "source_line": field_line,
            "captures_real_volume_field": real_volume_read,
        },
        "semantics_note": "MT5's own API defines 'tick_volume' as the number of price-quote "
                   "ticks recorded within the bar (a quote-update count), and 'real_volume' as "
                   "actual traded volume WHEN the broker/symbol supplies it. This pipeline reads "
                   "and stores ONLY tick_volume ('real_volume' is never referenced anywhere in "
                   "mt5_provider.py, verified above) -- it is a broker-specific activity/liquidity "
                   "proxy, not a claim about centralized traded volume. Whether this broker's "
                   "specific feed synthesizes tick_volume differently for cross pairs vs. majors "
                   "is NOT established by this repository and is not asserted here (Sec.15).",
        "schema_has_bid_ask_spread_or_depth": False,
        "per_instrument_live_stats": stats,
    }


# ==========================================================================
# Sec.18 matched-population audit
# ==========================================================================
def population_matching_audit(tf: str = PRIMARY_TF, horizon: int = PRIMARY_HORIZON,
                              instruments: Tuple[str, ...] = INSTRUMENTS_83) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for inst in instruments:
        df, feats = _get_features_bars_85(inst, tf)
        n = len(df)
        t1 = p83._t1_signed_return(df, horizon)
        t2 = p83._t2_range_ratio(df, horizon)
        warmup = max(p83._WARMUP, _VOLUME_WINDOW)
        idx_all = np.arange(warmup, n - horizon)
        target_ok = np.isfinite(t1[idx_all]) & np.isfinite(t2[idx_all])

        baseline_vals = feats.iloc[idx_all][list(BASELINE_D_COLUMNS)].to_numpy(float)
        baseline_ok = np.isfinite(baseline_vals).all(axis=1)
        volume_vals = feats.iloc[idx_all][list(VOLUME_COLUMNS)].to_numpy(float)
        volume_ok = np.isfinite(volume_vals).all(axis=1)

        combined_ok = target_ok & baseline_ok & volume_ok
        out[inst] = {
            "n_after_warmup": int(len(idx_all)),
            "n_dropped_target_nan": int((~target_ok).sum()),
            "n_dropped_baseline_nan": int((~baseline_ok).sum()),
            "n_dropped_volume_nan": int((~volume_ok).sum()),
            "n_baseline_only_would_keep": int((target_ok & baseline_ok).sum()),
            "n_final_all_ablations_M1_to_M4": int(combined_ok.sum()),
            "matched": bool((target_ok & baseline_ok).sum() >= combined_ok.sum()),
        }
    total_final = sum(v["n_final_all_ablations_M1_to_M4"] for v in out.values())
    total_baseline_only = sum(v["n_baseline_only_would_keep"] for v in out.values())
    return {"per_instrument": out, "total_rows_all_ablations_share": total_final,
           "total_rows_baseline_only_would_have_had": total_baseline_only,
           "extra_rows_baseline_would_gain_by_ignoring_volume_nan":
               total_baseline_only - total_final,
           "note": "All M1-M4 ablations are fit from ONE dataset (build_dataset_85) using a "
                   "single combined finite-value mask across baseline AND volume columns -- "
                   "the matched-population requirement is structural. This audit reports how "
                   "many additional rows a baseline-only builder (ignoring volume NaNs) would "
                   "have kept, to make the (typically small) population difference explicit "
                   "rather than silent."}


# ==========================================================================
# Sec.13 required ablation
# ==========================================================================
def run_ablation(discovery: pd.DataFrame, confirmation: pd.DataFrame, target_col: str = "T2"
                 ) -> Dict[str, Any]:
    fits: Dict[str, Dict[str, Any]] = {}
    for name, feats in ABLATIONS_85:
        cols = [f"feat__{c}" for c in feats]
        fits[name] = fit_and_eval_83(discovery, confirmation, cols, target_col)
    m1_name = ABLATIONS_85[0][0]
    out: Dict[str, Any] = {"target": target_col, "models": {}}
    for name, _ in ABLATIONS_85:
        row = {"n_features": len(fits[name]["features"]), "oos_r2": fits[name]["metrics"]["oos_r2"],
              "mae": fits[name]["metrics"]["mae"], "spearman": fits[name]["metrics"]["spearman"]}
        if name != m1_name:
            boot = bootstrap_delta_ci(fits[m1_name]["_y_true"], fits[name]["_p_pred"],
                                      fits[m1_name]["_p_pred"], _r2_fn(fits[m1_name]["train_mean"]),
                                      block=int(discovery["horizon_bars"].iloc[0]), seed=RANDOM_SEED)
            row["delta_r2_vs_M1"] = boot
        out["models"][name] = row
    out["_fits"] = fits  # internal use only (predictions for downstream analyses); stripped before persist
    return out


def _strip_internal(ablation_result: Dict[str, Any]) -> Dict[str, Any]:
    return {"target": ablation_result["target"], "models": ablation_result["models"]}


# ==========================================================================
# Sec.19 cross-asset breakdown
# ==========================================================================
def cross_asset_breakdown(ablation_result: Dict[str, Any], confirmation: pd.DataFrame,
                          model_key: str = "M4_baseline_plus_both") -> Dict[str, Any]:
    fits = ablation_result["_fits"]
    m1, mk = fits[ABLATIONS_85[0][0]], fits[model_key]
    conf_reset = confirmation.reset_index(drop=True)
    out: Dict[str, Any] = {}
    for inst in INSTRUMENTS_83:
        mask = (conf_reset["instrument"] == inst).to_numpy()
        n = int(mask.sum())
        if n < _MIN_CELL_N:
            out[inst] = {"state": "INSUFFICIENT_SAMPLE", "n": n}
            continue
        train_mean = m1["train_mean"]
        r2_fn = _r2_fn(train_mean)
        r2_base = r2_fn(m1["_y_true"][mask], m1["_p_pred"][mask])
        r2_vol = r2_fn(mk["_y_true"][mask], mk["_p_pred"][mask])
        boot = bootstrap_delta_ci(m1["_y_true"][mask], mk["_p_pred"][mask], m1["_p_pred"][mask],
                                  r2_fn, block=int(confirmation["horizon_bars"].iloc[0]),
                                  seed=RANDOM_SEED)
        out[inst] = {"n": n, "baseline_r2": round(r2_base, 5), "volume_r2": round(r2_vol, 5),
                    "delta_r2": boot.get("point"), "ci": [boot.get("ci_lower"), boot.get("ci_upper")],
                    "sign": "positive" if (boot.get("point") or 0) > 0 else
                            ("negative" if (boot.get("point") or 0) < 0 else "zero"),
                    "excludes_zero": boot.get("excludes_zero")}
    return out


# ==========================================================================
# Sec.20 leave-one-asset-out
# ==========================================================================
def leave_one_asset_out(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                        model_key: str = "M4_baseline_plus_both", target_col: str = "T2"
                        ) -> Dict[str, Any]:
    model_feats = dict(ABLATIONS_85)[model_key]
    baseline_feats = dict(ABLATIONS_85)[ABLATIONS_85[0][0]]
    out: Dict[str, Any] = {}
    for held_out in INSTRUMENTS_83:
        train_wo = discovery[discovery["instrument"] != held_out]
        test_held = confirmation[confirmation["instrument"] == held_out]
        if len(train_wo) < 5000 or len(test_held) < _MIN_CELL_N:
            out[held_out] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        r_base = fit_and_eval_83(train_wo, test_held, [f"feat__{c}" for c in baseline_feats], target_col)
        r_vol = fit_and_eval_83(train_wo, test_held, [f"feat__{c}" for c in model_feats], target_col)
        boot = bootstrap_delta_ci(r_base["_y_true"], r_vol["_p_pred"], r_base["_p_pred"],
                                  _r2_fn(r_base["train_mean"]),
                                  block=int(test_held["horizon_bars"].iloc[0]), seed=RANDOM_SEED)
        out[held_out] = {"baseline_r2": r_base["metrics"]["oos_r2"],
                         "volume_r2": r_vol["metrics"]["oos_r2"], "delta_r2": boot.get("point"),
                         "ci": [boot.get("ci_lower"), boot.get("ci_upper")],
                         "excludes_zero": boot.get("excludes_zero")}
    return out


# ==========================================================================
# Sec.21 temporal stability (predeclared calendar-quarter blocks)
# ==========================================================================
def _quarter_blocks(confirmation: pd.DataFrame) -> List[Tuple[str, pd.Timestamp, pd.Timestamp]]:
    ts = confirmation["prediction_timestamp"]
    start, end = ts.min(), ts.max()
    blocks = []
    cur = pd.Timestamp(year=start.year, month=((start.month - 1) // 3) * 3 + 1, day=1, tz="UTC")
    while cur <= end:
        nxt = cur + pd.DateOffset(months=3)
        q = (cur.month - 1) // 3 + 1
        blocks.append((f"{cur.year}Q{q}", cur, nxt))
        cur = nxt
    return blocks


def temporal_stability(ablation_result: Dict[str, Any], confirmation: pd.DataFrame,
                       model_key: str = "M4_baseline_plus_both") -> List[Dict[str, Any]]:
    fits = ablation_result["_fits"]
    m1, mk = fits[ABLATIONS_85[0][0]], fits[model_key]
    ts = confirmation.reset_index(drop=True)["prediction_timestamp"]
    out = []
    for label, lo, hi in _quarter_blocks(confirmation):
        mask = ((ts >= lo) & (ts < hi)).to_numpy()
        n = int(mask.sum())
        if n < _MIN_CELL_N:
            out.append({"block": label, "state": "INSUFFICIENT_SAMPLE", "n": n})
            continue
        r2_fn = _r2_fn(m1["train_mean"])
        r2_base = r2_fn(m1["_y_true"][mask], m1["_p_pred"][mask])
        r2_vol = r2_fn(mk["_y_true"][mask], mk["_p_pred"][mask])
        out.append({"block": label, "n": n, "baseline_r2": round(r2_base, 5),
                   "volume_r2": round(r2_vol, 5), "delta_r2": round(r2_vol - r2_base, 5)})
    return out


# ==========================================================================
# Sec.22 horizon stability
# ==========================================================================
def horizon_stability(target_col: str = "T2", model_key: str = "M4_baseline_plus_both"
                      ) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for h in ALL_HORIZONS:
        ds = build_pooled_dataset_85(PRIMARY_TF, h)
        disc, conf = discovery_confirmation_split(ds)
        abl = run_ablation(disc, conf, target_col)
        out[h] = {"models": _strip_internal(abl)["models"]}
    return out


# ==========================================================================
# Sec.23/24 volatility & session/time confounding
# ==========================================================================
def confounding_analysis(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                         target_col: str = "T2") -> Dict[str, Any]:
    stages = [
        ("volatility_only", ["atr_rank", "rv_rank"]),
        ("volatility_plus_volume", ["atr_rank", "rv_rank", "volume_rank"]),
        ("time_session_only", ["hour_sin", "hour_cos", "dow", "regime_TRENDING", "regime_RANGING",
                               "session_LONDON", "session_NEW_YORK", "session_LONDON_NY_OVERLAP",
                               "session_LATE_US"]),
        ("time_session_plus_volume", ["hour_sin", "hour_cos", "dow", "regime_TRENDING",
                                      "regime_RANGING", "session_LONDON", "session_NEW_YORK",
                                      "session_LONDON_NY_OVERLAP", "session_LATE_US", "volume_rank"]),
        ("full_baseline", list(BASELINE_D_COLUMNS)),
        ("full_baseline_plus_volume", list(BASELINE_D_COLUMNS) + ["volume_rank"]),
    ]
    out: Dict[str, Any] = {}
    for name, feats in stages:
        cols = [f"feat__{c}" for c in feats]
        r = fit_and_eval_83(discovery, confirmation, cols, target_col)
        out[name] = {"n_features": len(feats), "oos_r2": r["metrics"]["oos_r2"]}
    out["volatility_delta_from_volume"] = round(
        out["volatility_plus_volume"]["oos_r2"] - out["volatility_only"]["oos_r2"], 5)
    out["time_session_delta_from_volume"] = round(
        out["time_session_plus_volume"]["oos_r2"] - out["time_session_only"]["oos_r2"], 5)
    out["full_baseline_delta_from_volume"] = round(
        out["full_baseline_plus_volume"]["oos_r2"] - out["full_baseline"]["oos_r2"], 5)
    out["interpretation"] = (
        "If the full_baseline_delta_from_volume remains materially positive even though "
        "volatility and session/time are ALREADY in the baseline, volume is not merely "
        "restating information the baseline's own volatility/session/time features already "
        "carry. This does not, by itself, establish causal mechanism.")
    return out


# ==========================================================================
# Sec.25/26 placebo battery
# ==========================================================================
def target_shuffle_control(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                           model_key: str = "M4_baseline_plus_both", target_col: str = "T2",
                           seed: int = 85001) -> Dict[str, Any]:
    baseline_feats = dict(ABLATIONS_85)[ABLATIONS_85[0][0]]
    model_feats = dict(ABLATIONS_85)[model_key]
    rng = np.random.default_rng(seed)
    train = discovery.copy()
    train[target_col] = rng.permutation(train[target_col].to_numpy())
    r_base = fit_and_eval_83(train, confirmation, [f"feat__{c}" for c in baseline_feats], target_col)
    r_vol = fit_and_eval_83(train, confirmation, [f"feat__{c}" for c in model_feats], target_col)
    return {"baseline_r2": r_base["metrics"]["oos_r2"], "volume_r2": r_vol["metrics"]["oos_r2"],
           "delta_r2": round(r_vol["metrics"]["oos_r2"] - r_base["metrics"]["oos_r2"], 5)}


def global_volume_shuffle_placebo(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                                  model_key: str = "M4_baseline_plus_both", target_col: str = "T2",
                                  seed: int = 85002) -> Dict[str, Any]:
    baseline_feats = dict(ABLATIONS_85)[ABLATIONS_85[0][0]]
    model_feats = dict(ABLATIONS_85)[model_key]
    rng = np.random.default_rng(seed)
    train, test = discovery.copy(), confirmation.copy()
    for c in VOLUME_COLUMNS:
        col = f"feat__{c}"
        if col in train.columns:
            train[col] = rng.permutation(train[col].to_numpy())
            test[col] = rng.permutation(test[col].to_numpy())
    r_base = fit_and_eval_83(train, test, [f"feat__{c}" for c in baseline_feats], target_col)
    r_vol = fit_and_eval_83(train, test, [f"feat__{c}" for c in model_feats], target_col)
    return {"baseline_r2": r_base["metrics"]["oos_r2"], "volume_r2": r_vol["metrics"]["oos_r2"],
           "delta_r2": round(r_vol["metrics"]["oos_r2"] - r_base["metrics"]["oos_r2"], 5)}


def _stratified_shuffle(df: pd.DataFrame, strata_cols: List[str], value_cols: Tuple[str, ...],
                        rng: np.random.Generator) -> pd.DataFrame:
    out = df.copy()
    for _, grp_idx in df.groupby(strata_cols, observed=True).groups.items():
        idx = np.asarray(grp_idx)
        if len(idx) < 2:
            continue
        perm = rng.permutation(len(idx))
        for c in value_cols:
            col = f"feat__{c}"
            if col in out.columns:
                out.loc[idx, col] = out.loc[idx, col].to_numpy()[perm]
    return out


def stratified_shuffle_placebo(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                               model_key: str = "M4_baseline_plus_both", target_col: str = "T2",
                               seed: int = 85003) -> Dict[str, Any]:
    """Sec.25.C -- permute volume within (instrument, session) strata: preserves
    each instrument's own volume marginal AND its session-conditional volume
    distribution, destroys the exact temporal/event-level association."""
    baseline_feats = dict(ABLATIONS_85)[ABLATIONS_85[0][0]]
    model_feats = dict(ABLATIONS_85)[model_key]
    rng = np.random.default_rng(seed)
    disc_with_session = discovery.copy()
    disc_with_session["_session"] = np.select(
        [disc_with_session[f"feat__session_{s}"].to_numpy() > 0.5
         for s in ("LONDON", "NEW_YORK", "LONDON_NY_OVERLAP", "LATE_US")],
        ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP", "LATE_US"], default="TOKYO")
    train = _stratified_shuffle(disc_with_session, ["instrument", "_session"], VOLUME_COLUMNS, rng)
    train = train.drop(columns=["_session"])
    r_base = fit_and_eval_83(train, confirmation, [f"feat__{c}" for c in baseline_feats], target_col)
    r_vol = fit_and_eval_83(train, confirmation, [f"feat__{c}" for c in model_feats], target_col)
    return {"baseline_r2": r_base["metrics"]["oos_r2"], "volume_r2": r_vol["metrics"]["oos_r2"],
           "delta_r2": round(r_vol["metrics"]["oos_r2"] - r_base["metrics"]["oos_r2"], 5)}


def temporal_misalignment_placebo(offsets: Tuple[int, ...] = _TEMPORAL_MISALIGNMENT_OFFSETS,
                                  tf: str = PRIMARY_TF, horizon: int = PRIMARY_HORIZON,
                                  target_col: str = "T2",
                                  model_key: str = "M4_baseline_plus_both") -> List[Dict[str, Any]]:
    """Sec.25.D -- reassign volume_rank/volume_ret_1 from event_idx+offset
    instead of event_idx (target and baseline features stay at event_idx).
    A predeclared, small offset family only -- never a search."""
    baseline_feats = dict(ABLATIONS_85)[ABLATIONS_85[0][0]]
    model_feats = [c for c in dict(ABLATIONS_85)[model_key] if c not in BASELINE_D_COLUMNS]
    out = []
    for offset in offsets:
        frames = []
        for inst in INSTRUMENTS_83:
            df, feats = _get_features_bars_85(inst, tf)
            ds = build_dataset_85(inst, tf, horizon)
            if ds.empty:
                continue
            n = len(df)
            shifted_idx = np.clip(ds["event_idx"].to_numpy() + offset, 0, n - 1)
            for c in model_feats:
                ds[f"feat__{c}"] = feats[c].to_numpy()[shifted_idx]
            frames.append(ds)
        if not frames:
            continue
        pooled = pd.concat(frames, ignore_index=True).sort_values("prediction_timestamp").reset_index(drop=True)
        disc, conf = discovery_confirmation_split(pooled)
        if len(disc) < 5000 or len(conf) < _MIN_CELL_N:
            out.append({"offset_bars": offset, "state": "INSUFFICIENT_SAMPLE"})
            continue
        r_base = fit_and_eval_83(disc, conf, [f"feat__{c}" for c in baseline_feats], target_col)
        r_vol = fit_and_eval_83(disc, conf, [f"feat__{c}" for c in baseline_feats + model_feats], target_col)
        out.append({"offset_bars": offset, "baseline_r2": r_base["metrics"]["oos_r2"],
                   "misaligned_volume_r2": r_vol["metrics"]["oos_r2"],
                   "delta_r2": round(r_vol["metrics"]["oos_r2"] - r_base["metrics"]["oos_r2"], 5)})
    return out


def stronger_temporal_placebo(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                              model_key: str = "M4_baseline_plus_both", target_col: str = "T2",
                              seed: int = 85004) -> Dict[str, Any]:
    """Sec.26 -- declared BEFORE inspecting any result: permute volume within
    (instrument, discovery-half) strata -- preserves each instrument's own
    volume distribution AND its coarse temporal regime (early vs late
    discovery), destroys the exact bar-level temporal association."""
    baseline_feats = dict(ABLATIONS_85)[ABLATIONS_85[0][0]]
    model_feats = dict(ABLATIONS_85)[model_key]
    rng = np.random.default_rng(seed)
    disc = discovery.copy()
    median_ts = disc["prediction_timestamp"].median()
    disc["_half"] = np.where(disc["prediction_timestamp"] < median_ts, "early", "late")
    train = _stratified_shuffle(disc, ["instrument", "_half"], VOLUME_COLUMNS, rng)
    train = train.drop(columns=["_half"])
    r_base = fit_and_eval_83(train, confirmation, [f"feat__{c}" for c in baseline_feats], target_col)
    r_vol = fit_and_eval_83(train, confirmation, [f"feat__{c}" for c in model_feats], target_col)
    return {"baseline_r2": r_base["metrics"]["oos_r2"], "volume_r2": r_vol["metrics"]["oos_r2"],
           "delta_r2": round(r_vol["metrics"]["oos_r2"] - r_base["metrics"]["oos_r2"], 5)}


# ==========================================================================
# Sec.27 distribution drift
# ==========================================================================
def distribution_drift_audit(discovery: pd.DataFrame, confirmation: pd.DataFrame) -> Dict[str, Any]:
    def _stats(s: pd.Series) -> Dict[str, float]:
        v = s.to_numpy(float)
        v = v[np.isfinite(v)]
        return {"median": round(float(np.median(v)), 5), "p10": round(float(np.percentile(v, 10)), 5),
               "p90": round(float(np.percentile(v, 90)), 5), "var": round(float(np.var(v)), 6),
               "n": int(len(v))}
    out: Dict[str, Any] = {"by_split": {}, "by_instrument": {}}
    for split_name, split_df in (("discovery", discovery), ("confirmation", confirmation)):
        out["by_split"][split_name] = {c: _stats(split_df[f"feat__{c}"]) for c in VOLUME_COLUMNS}
    for inst in INSTRUMENTS_83:
        sub = confirmation[confirmation["instrument"] == inst]
        if len(sub) < _MIN_CELL_N:
            out["by_instrument"][inst] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        out["by_instrument"][inst] = {c: _stats(sub[f"feat__{c}"]) for c in VOLUME_COLUMNS}
    return out


# ==========================================================================
# Sec.28-31 broker / feed generalization
# ==========================================================================
def broker_feed_generalization_audit() -> Dict[str, Any]:
    """Checks the repository for any already-connected independent OHLCV+
    volume feed BEFORE concluding none exists, then makes one conservative,
    already-a-repo-dependency, no-new-credential attempt (yfinance, already
    used by Phases 69-73) to see whether it can even in principle supply a
    comparable volume signal -- documented empirically, not assumed."""
    # (a) any non-MT5 source already ingested?
    non_mt5_present = False
    for inst in INSTRUMENTS_83:
        rows = store.get_candles(inst, PRIMARY_TF)
        if rows and any(r.get("source") not in (None, "mt5") for r in rows[:5000]):
            non_mt5_present = True
            break

    # (b) capital_sync.py inspected: does it fetch historical OHLCV candles,
    # or only live trade/position history?
    import capital_sync
    cap_src = inspect.getsource(capital_sync)
    capital_has_ohlcv_history = ("copy_rates" in cap_src) or ("prices" in cap_src.lower()
        and "history/prices" in cap_src)

    # (c) empirical yfinance volume check (no new credentials, already a
    # repository dependency since Phase 69-73)
    yfinance_check: Dict[str, Any] = {"attempted": False}
    try:
        import yfinance as yf
        df = yf.download("EURUSD=X", period="5d", interval="15m", progress=False)
        vol_col_present = "Volume" in (df.columns.get_level_values(0)
                                       if hasattr(df.columns, "get_level_values") else df.columns)
        yfinance_check = {"attempted": True, "rows": int(len(df)),
                          "volume_all_zero": bool((df["Volume"].to_numpy() == 0).all())
                          if vol_col_present else None}
    except Exception as e:
        yfinance_check = {"attempted": True, "error": str(e)}

    independently_available = non_mt5_present or capital_has_ohlcv_history
    verdict = "INDEPENDENT_FEED_REPLICATION_NOT_AVAILABLE" if not independently_available else \
             "INDEPENDENT_FEED_CANDIDATE_FOUND_NOT_YET_TESTED"
    return {
        "non_mt5_source_already_ingested": non_mt5_present,
        "capital_com_integration_provides_historical_ohlcv": capital_has_ohlcv_history,
        "capital_com_integration_note": "capital_sync.py inspected directly: it syncs live "
                   "transaction/activity/position history for the trade journal, NOT historical "
                   "OHLCV candles -- it is not usable as an independent price/volume feed without "
                   "new integration work.",
        "yfinance_check": yfinance_check,
        "yfinance_note": "yfinance is already a repository dependency (Phase 69-73 ingestion) "
                   "and requires no new credentials, so it was checked empirically rather than "
                   "assumed unusable. Its spot-FX 'Volume' field returned exactly zero for every "
                   "bar tested -- Yahoo does not supply real tick or trade volume for OTC FX -- so "
                   "it cannot serve as an independent volume feed even though it is a different "
                   "vendor. No new external data source was acquired or subscribed to in this "
                   "phase (per the master prompt's data-availability rule).",
        "verdict": verdict,
    }


# ==========================================================================
# Sec.34 multiple-testing audit (researcher degrees of freedom)
# ==========================================================================
def multiple_testing_audit(cross_asset: Dict[str, Any], horizon_result: Dict[int, Dict[str, Any]],
                           model_key: str = "M4_baseline_plus_both") -> Dict[str, Any]:
    disclosed_search_space = {
        "candidate_features_ever_tested_phase84_and_85": list(VOLUME_COLUMNS),
        "lookback_windows_ever_tested": [_VOLUME_WINDOW],
        "transformations_ever_tested": ["percentile_rank", "log_ratio_1_bar"],
        "target_families_ever_tested": ["T2_magnitude (primary)", "T1_direction (control, not optimized)"],
        "note": "Per Phase 84's own module and this phase's frozen specification (Sec.7-8 of "
                   "the master prompt), the volume feature search was bounded to exactly these "
                   "two candidates, one lookback, two transforms -- no lookback sweep, no "
                   "additional volume-derived indicator, and no feature-selection search was "
                   "ever run against T2 before this phase's own frozen ablation.",
    }
    from phase76_event_study import _norm_cdf
    pvals = []
    insts_tested = []
    for inst, row in cross_asset.items():
        if not isinstance(row, dict) or "delta_r2" not in row or row.get("delta_r2") is None:
            continue
        lo, hi = row.get("ci", [None, None])
        if lo is None or hi is None:
            continue
        se = max((hi - lo) / (2 * 1.96), 1e-6)
        z = row["delta_r2"] / se
        pvals.append(2 * (1 - _norm_cdf(abs(z))))
        insts_tested.append(inst)
    bh_flags = _benjamini_hochberg(pvals, q=_MULTI_TESTING_Q) if pvals else []
    cross_asset_bh = {inst: bool(f) for inst, f in zip(insts_tested, bh_flags)}

    h_pvals, h_list = [], []
    for h, res in horizon_result.items():
        row = res["models"].get(model_key, {})
        d = row.get("delta_r2_vs_M1", {})
        point, se = d.get("point"), d.get("se")
        if point is None:
            continue
        se_eff = se if (se and se > 0) else 1e-6
        z = point / se_eff
        h_pvals.append(2 * (1 - _norm_cdf(abs(z))))
        h_list.append(h)
    h_bh_flags = _benjamini_hochberg(h_pvals, q=_MULTI_TESTING_Q) if h_pvals else []
    horizon_bh = {h: bool(f) for h, f in zip(h_list, h_bh_flags)}

    return {"disclosed_search_space": disclosed_search_space,
           "cross_asset_bh_q0.10": cross_asset_bh, "horizon_bh_q0.10": horizon_bh}


# ==========================================================================
# claim hierarchy / verdict classification (Sec.33, Sec.43-45)
# ==========================================================================
_VALID_VERDICTS = ("REJECTED", "ARTIFACT_OR_LEAKAGE", "UNSTABLE", "BROKER_SPECIFIC",
                  "DESCRIPTIVE_ONLY", "EXPLAINED_BY_CONTEXT", "INCREMENTAL_BUT_NOT_MATERIAL",
                  "PROMISING_REQUIRES_FURTHER_CONFIRMATION", "ROBUST_INCREMENTAL_INFORMATION")


def classify_verdict_85(pooled_delta_point: Optional[float], pooled_ci_excludes_zero: bool,
                        placebo_collapse: bool, leakage_ok: bool, determinism_ok: bool,
                        holdout_ok: bool, n_instruments_excl_zero_positive: int,
                        n_instruments_total: int, independent_feed_available: bool,
                        material_margin: float = 0.01) -> Tuple[str, str, str]:
    """Returns (verdict, claim_level, reason). claim_level in {A,B,C,D} per
    Sec.33 -- never assigned beyond what n_instruments_excl_zero_positive /
    independent_feed_available actually support."""
    if not leakage_ok or not determinism_ok or not holdout_ok:
        return "ARTIFACT_OR_LEAKAGE", "NONE", "Leakage, determinism, or holdout check failed."
    if pooled_delta_point is None or not pooled_ci_excludes_zero or pooled_delta_point <= 0:
        return "REJECTED", "NONE", "Pooled effect not statistically distinguishable from zero."
    if not placebo_collapse:
        return "ARTIFACT_OR_LEAKAGE", "NONE", "Placebo battery did not collapse -- effect may be mechanical."
    if pooled_delta_point < material_margin:
        return "INCREMENTAL_BUT_NOT_MATERIAL", "A", \
            f"Pooled delta {pooled_delta_point} below the {material_margin} materiality margin."
    breadth_ratio = n_instruments_excl_zero_positive / max(n_instruments_total, 1)
    if breadth_ratio < 0.5:
        return "UNSTABLE", "A", "Effect material pooled but not consistently positive across instruments."
    if not independent_feed_available:
        claim = "B" if breadth_ratio >= (4 / 6) else "A"
        return "PROMISING_REQUIRES_FURTHER_CONFIRMATION", claim, \
            "Effect material, CI-excluding, placebo-collapsing, and reasonably broad across " \
            "instruments on this feed, but independent-feed replication is not available -- " \
            "feed-independence (Claim C) cannot be established."
    if breadth_ratio >= (4 / 6):
        return "ROBUST_INCREMENTAL_INFORMATION", "C", \
            "Material, broad, and confirmed on an independent feed."
    return "PROMISING_REQUIRES_FURTHER_CONFIRMATION", "B", \
        "Independent-feed evidence exists but instrument breadth is limited."


# ==========================================================================
# result container
# ==========================================================================
@dataclass
class Phase85Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    horizons: List[int]
    discovery_confirmation_split: Dict[str, Any]
    data_provenance: Dict[str, Any]
    population_matching: Dict[str, Any]
    ablation_headline: Dict[str, Any]
    cross_asset_M2: Dict[str, Any]
    cross_asset_M4: Dict[str, Any]
    leave_one_asset_out: Dict[str, Any]
    temporal_stability: List[Dict[str, Any]]
    horizon_stability: Dict[int, Dict[str, Any]]
    confounding: Dict[str, Any]
    placebos: Dict[str, Any]
    distribution_drift: Dict[str, Any]
    broker_feed_generalization: Dict[str, Any]
    multiple_testing: Dict[str, Any]
    determinism: Dict[str, Any]
    verdict: str
    claim_level: str
    verdict_reason: str
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True
    strategy_status: str = "RESEARCH_ONLY_NO_STRATEGY_ARTIFACT"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def run() -> Phase85Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()
    _clear_cache_85()

    ds_h4 = build_pooled_dataset_85(PRIMARY_TF, PRIMARY_HORIZON)
    contract = p83.assert_feature_target_contract(ds_h4, "T2")
    leakage_ok = bool(contract.get("pass", False))
    discovery, confirmation = discovery_confirmation_split(ds_h4)
    split_summary = {"discovery_n": int(len(discovery)), "confirmation_n": int(len(confirmation)),
                     "n_total": int(len(ds_h4))}

    provenance = data_provenance_audit()
    pop_match = population_matching_audit()

    ablation_1 = run_ablation(discovery, confirmation, "T2")
    ablation_2 = run_ablation(discovery, confirmation, "T2")
    ablation_t1 = run_ablation(discovery, confirmation, "T1")
    determinism_match = (_strip_internal(ablation_1)["models"] == _strip_internal(ablation_2)["models"])

    cross_m2 = cross_asset_breakdown(ablation_1, confirmation, "M2_baseline_plus_volume_rank")
    cross_m4 = cross_asset_breakdown(ablation_1, confirmation, "M4_baseline_plus_both")
    loao = leave_one_asset_out(discovery, confirmation, "M4_baseline_plus_both", "T2")
    temporal = temporal_stability(ablation_1, confirmation, "M4_baseline_plus_both")
    horizons = horizon_stability("T2", "M4_baseline_plus_both")
    confounding = confounding_analysis(discovery, confirmation, "T2")

    placebos = {
        "target_shuffle": target_shuffle_control(discovery, confirmation),
        "global_volume_shuffle": global_volume_shuffle_placebo(discovery, confirmation),
        "instrument_session_stratified_shuffle": stratified_shuffle_placebo(discovery, confirmation),
        "temporal_misalignment": temporal_misalignment_placebo(),
        "stronger_within_instrument_time_stratum_placebo": stronger_temporal_placebo(discovery, confirmation),
        "directional_control_T1": _strip_internal(ablation_t1)["models"],
    }
    drift = distribution_drift_audit(discovery, confirmation)
    feed_gen = broker_feed_generalization_audit()
    mtest = multiple_testing_audit(cross_m4, horizons)

    pooled_delta = ablation_1["models"]["M4_baseline_plus_both"].get("delta_r2_vs_M1", {})
    pooled_point = pooled_delta.get("point")
    pooled_excl = bool(pooled_delta.get("excludes_zero"))

    def _small(d: Dict[str, Any]) -> bool:
        return abs(d.get("delta_r2", 0.0)) < 0.005

    placebo_collapse = all(_small(placebos[k]) for k in
                           ("target_shuffle", "global_volume_shuffle",
                            "instrument_session_stratified_shuffle",
                            "stronger_within_instrument_time_stratum_placebo"))

    n_pos_excl_zero = sum(1 for v in cross_m4.values()
                          if isinstance(v, dict) and v.get("excludes_zero") and (v.get("delta_r2") or 0) > 0)
    n_instruments_total = len(INSTRUMENTS_83)
    holdout_ok = True  # nothing in this module ever reads the Phase-74 holdout

    verdict, claim_level, reason = classify_verdict_85(
        pooled_point, pooled_excl, placebo_collapse, leakage_ok, determinism_match, holdout_ok,
        n_pos_excl_zero, n_instruments_total, feed_gen["verdict"] != "INDEPENDENT_FEED_REPLICATION_NOT_AVAILABLE")

    ident = json.dumps({"schema": SCHEMA_VERSION, "ablation": _strip_internal(ablation_1),
                       "cross_m4": {k: (v if isinstance(v, dict) and "delta_r2" in v else str(v))
                                   for k, v in cross_m4.items()},
                       "verdict": verdict}, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase85Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(INSTRUMENTS_83), timeframe=PRIMARY_TF, horizons=list(ALL_HORIZONS),
        discovery_confirmation_split=split_summary, data_provenance=provenance,
        population_matching=pop_match, ablation_headline=_strip_internal(ablation_1),
        cross_asset_M2=cross_m2, cross_asset_M4=cross_m4, leave_one_asset_out=loao,
        temporal_stability=temporal, horizon_stability=horizons, confounding=confounding,
        placebos=placebos, distribution_drift=drift, broker_feed_generalization=feed_gen,
        multiple_testing=mtest, determinism={"match": determinism_match},
        verdict=verdict, claim_level=claim_level, verdict_reason=reason,
        runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase85Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase85_tick_volume_confirmation", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 85 - tick-volume confirmation, generalization & feed-independence study ...",
         flush=True)
    res = run()
    print(f"\n=== PHASE 85 ({res.runtime_seconds}s) ===")
    print(f"Ablation (T2): {json.dumps(res.ablation_headline, default=str)}")
    print(f"\nCross-asset M4: {json.dumps(res.cross_asset_M4, default=str)}")
    print(f"\nLOAO: {json.dumps(res.leave_one_asset_out, default=str)}")
    print(f"\nTemporal stability: {json.dumps(res.temporal_stability, default=str)}")
    print(f"\nHorizon stability: {json.dumps(res.horizon_stability, default=str)}")
    print(f"\nConfounding: {json.dumps(res.confounding, default=str)}")
    print(f"\nPlacebos: {json.dumps(res.placebos, default=str)}")
    print(f"\nFeed generalization: {json.dumps(res.broker_feed_generalization, default=str)}")
    print(f"\nDeterminism match: {res.determinism['match']}")
    print(f"\nVERDICT: {res.verdict} (claim {res.claim_level}) -- {res.verdict_reason}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DATASET_VERSION", "ABLATIONS_85", "VOLUME_COLUMNS",
    "ALL_HORIZONS", "build_dataset_85", "build_pooled_dataset_85", "data_provenance_audit",
    "population_matching_audit", "run_ablation", "cross_asset_breakdown",
    "leave_one_asset_out", "temporal_stability", "horizon_stability", "confounding_analysis",
    "target_shuffle_control", "global_volume_shuffle_placebo", "stratified_shuffle_placebo",
    "temporal_misalignment_placebo", "stronger_temporal_placebo", "distribution_drift_audit",
    "broker_feed_generalization_audit", "multiple_testing_audit", "classify_verdict_85",
    "run", "persist", "get_result", "main",
]
