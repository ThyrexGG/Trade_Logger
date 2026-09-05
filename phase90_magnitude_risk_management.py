# -*- coding: utf-8 -*-
"""
Phase 90 -- Cost-Aware Magnitude Risk-Management Validation.

Tests Claim C, not Claim A or B (already settled): does Phase 89's
confirmed tick-volume magnitude signal (Claim B: SUPPORTED) improve a
realistic risk-management decision enough to survive costs and
out-of-sample validation? This is explicitly NOT a directional-discovery
phase -- Claim A (tick volume predicts direction) remains FALSE/NOT FOUND
(Phases 83/86/87/88) and is not reopened here.

Directional overlay (master prompt Sec.10, option 2 -- a fixed, explicitly
documented external-direction benchmark): every trade opportunity is
assigned direction = +1 ("always long"). This is deliberately NOT a
trading signal and is not expected to have positive expectancy on its
own -- it exists only to hold direction IDENTICAL between the baseline
and magnitude-aware systems, so any measured difference between them can
only come from the risk-management layer, never from direction. Reusing
`sign(mom_4)` (Phase 86's own tested-and-rejected construction) was
deliberately avoided, both because it is already known non-predictive and
because reusing it here could read as smuggling a directional claim back
in through the side door (Sec.5's explicit warning against turning Claim
B into Claim A).

Primary experiment (Sec.11, one predeclared design, never varied after
seeing results): on the pooled 6-instrument, 15m, horizon-4 dataset,
compare two risk-management systems that share the identical direction,
entry timing, and R-multiple construction (`direction * T1 - cost`, T1
reused unchanged from Phase 83):

  BASELINE       -- fixed position size (1.0x), no eligibility filter,
                    every warmed-up opportunity taken.
  MAGNITUDE-AWARE -- same fixed R-multiple construction, but (a) position
                    size is inverse-scaled by a train-only-calibrated,
                    walk-forward out-of-fold predicted-magnitude
                    percentile, capped to [0.5x, 1.5x] of baseline (a
                    volatility-targeting risk-management rule: reduce
                    exposure when a larger move is expected, increase it
                    when a smaller move is expected, common professional
                    practice, not "bet bigger on a big-move prediction"),
                    and (b) an eligibility filter skips the bottom
                    predeclared quartile of predicted target-reachability
                    (Application D: skip opportunities where the expected
                    move is too small to be worth the fixed cost).

Ablation: A0 (fixed size, no filter, no volatility features at all --
identical to BASELINE) / A1 (A0 + a volatility-only-conditioned sizing/
filter, no `volume_rank`) / A2 (A1 + `volume_rank`, i.e. the full
MAGNITUDE-AWARE system). The key comparison is A2 - A1: does tick volume
add value beyond ordinary volatility-based risk management, not merely
beyond doing nothing.

Reused, unchanged: Phase 83's frozen T1/T2 targets; Phase 89's frozen
`BASELINE_B_COLUMNS` (volatility-only) and pooled dataset construction;
Phase 80's frozen walk-forward fold machinery; Phase 76/86's cost-proxy
convention (BASE=0.05, ADVERSE=0.10, SEVERE=0.20 ATR). No new market
data, no paid data, no new directional signal. No live execution, no
broker transmission, no account-management mutation. The frozen Phase-74
Gold holdout is never read.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase76_event_study as p76
import phase80_ml_volatility_regime as p80
import phase82_compression_expansion_ml_pilot as p82
import phase83_conditional_interaction_discovery as p83
import phase84_information_frontier_audit as p84
import phase86_aggressive_edge_discovery as p86
import phase89_research_integrity_gate as p89
from phase76_event_study import RANDOM_SEED
from phase82_compression_expansion_ml_pilot import compute_regression_metrics
from phase83_conditional_interaction_discovery import INSTRUMENTS_83, PRIMARY_TF
from phase89_research_integrity_gate import BASELINE_B_COLUMNS, _HORIZON

SCHEMA_VERSION = "phase90.1"
ARTIFACT_KEY = "phase90_magnitude_risk_management"

COST_SCENARIOS: Dict[str, float] = dict(p86.COST_SCENARIOS)     # BASE/ADVERSE/SEVERE, reused unchanged
_MIN_CELL_N = 200
_SIZE_CAP: Tuple[float, float] = (0.5, 1.5)          # frozen sizing bounds, never optimized
_ELIGIBILITY_QUANTILE = 0.25                         # frozen: skip bottom quartile, predeclared
_FIXED_DIRECTION = 1.0                                # "always long" -- documented non-signal scaffold


# ==========================================================================
# dataset -- reuses Phase 89's Baseline B + volume_rank construction,
# extended with T1 (needed for the R-multiple P&L construction; Phase 89
# only carried T2)
# ==========================================================================
def build_dataset_90(instrument: str, tf: str = PRIMARY_TF, horizon: int = _HORIZON) -> pd.DataFrame:
    df = p76.load_bars(instrument, tf)
    if df.empty or len(df) < 2000:
        return pd.DataFrame()
    from phase78_market_behavior_discovery_ii import augment
    df = augment(df, tf)
    n = len(df)
    feats_b = p80._build_features(df)[list(BASELINE_B_COLUMNS)]
    vol_feats = p84._add_volume_features(df)
    feats = pd.concat([feats_b, vol_feats[["volume_rank"]]], axis=1)
    t1 = p83._t1_signed_return(df, horizon)
    t2 = p83._t2_range_ratio(df, horizon)

    warmup = max(200, p84._VOLUME_WINDOW)
    idx = np.arange(warmup, n - horizon)
    finite_mask = (np.isfinite(feats.iloc[idx].to_numpy(float)).all(axis=1)
                  & np.isfinite(t1[idx]) & np.isfinite(t2[idx]))
    idx = idx[finite_mask]
    if len(idx) == 0:
        return pd.DataFrame()

    from phase80_ml_volatility_regime import _TF_SECONDS
    tf_sec = _TF_SECONDS[tf]
    open_ts = df["t"].to_numpy(np.int64)
    pred_ts = pd.to_datetime(open_ts[idx].astype(np.int64) + tf_sec, unit="s", utc=True)
    targ_end_ts = pd.to_datetime(open_ts[idx + horizon].astype(np.int64) + tf_sec, unit="s", utc=True)
    hour = df["hour"].to_numpy(float)[idx]
    session = df["session"].to_numpy()[idx]
    out = pd.DataFrame({"instrument": instrument, "timeframe": tf, "horizon_bars": horizon,
                        "event_idx": idx, "prediction_timestamp": pred_ts,
                        "target_end_timestamp": targ_end_ts, "T1": t1[idx], "T2": t2[idx],
                        "hour": hour, "session": session})
    feat_rows = feats.iloc[idx].reset_index(drop=True)
    return pd.concat([out, feat_rows.add_prefix("feat__")], axis=1)


def build_pooled_dataset_90(tf: str = PRIMARY_TF, horizon: int = _HORIZON,
                            instruments: Tuple[str, ...] = INSTRUMENTS_83) -> pd.DataFrame:
    frames = [d for inst in instruments if not (d := build_dataset_90(inst, tf, horizon)).empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("prediction_timestamp").reset_index(drop=True)


# ==========================================================================
# walk-forward magnitude prediction (interface reused from Phase 89: Ridge,
# Phase 80's calendar-year folds) -- produces an out-of-fold, TRAIN-only-
# calibrated percentile for each test row, per model (A1 = volatility-only,
# A2 = + volume_rank)
# ==========================================================================
def _fit_predict_percentile(train: pd.DataFrame, test: pd.DataFrame, features: List[str],
                            target_col: str = "T2") -> Dict[str, np.ndarray]:
    model = Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0, random_state=RANDOM_SEED))])
    model.fit(train[features].to_numpy(float), train[target_col].to_numpy(float))
    train_pred = model.predict(train[features].to_numpy(float))
    test_pred = model.predict(test[features].to_numpy(float))
    # percentile of the TEST prediction against the TRAIN prediction
    # distribution only -- never against test itself (Sec.12/13: no
    # retrospective, test-set-informed calibration)
    train_sorted = np.sort(train_pred)
    test_percentile = np.searchsorted(train_sorted, test_pred, side="right") / len(train_sorted)
    train_percentile = np.searchsorted(train_sorted, train_pred, side="right") / len(train_sorted)
    return {"test_pred": test_pred, "test_percentile": np.clip(test_percentile, 0.0, 1.0),
           "train_percentile": np.clip(train_percentile, 0.0, 1.0),
           "eligibility_threshold": float(np.percentile(train_percentile, _ELIGIBILITY_QUANTILE * 100))}


def _apply_risk_system(test: pd.DataFrame, percentile: Optional[np.ndarray],
                       eligibility_threshold: Optional[float], cost_atr: float,
                       size_cap: Tuple[float, float] = _SIZE_CAP) -> Dict[str, Any]:
    """direction is FIXED (+1, 'always long', see module docstring). If
    percentile is None this is the BASELINE system (fixed size, no
    filter); otherwise it is a magnitude-aware system (volatility-
    targeting size, quartile eligibility filter)."""
    r_raw = _FIXED_DIRECTION * test["T1"].to_numpy(float)
    if percentile is None:
        size = np.ones(len(test))
        eligible = np.ones(len(test), dtype=bool)
    else:
        lo, hi = size_cap
        # inverse (volatility-targeting) sizing: higher predicted magnitude
        # percentile -> SMALLER size, within the frozen [lo, hi] cap
        size = np.clip(hi - (hi - lo) * percentile, lo, hi)
        eligible = percentile >= (eligibility_threshold if eligibility_threshold is not None else -1.0)
    net_r = (r_raw - cost_atr) * size
    net_r_eligible = net_r[eligible]
    return {"n_opportunities": int(len(test)), "n_eligible": int(eligible.sum()),
           "mean_size": round(float(size[eligible].mean()), 4) if eligible.any() else None,
           "net_r_series": net_r_eligible}


def _economic_metrics(net_r: np.ndarray) -> Dict[str, Any]:
    if len(net_r) == 0:
        return {"state": "NO_TRADES"}
    equity = np.cumsum(net_r)
    running_max = np.maximum.accumulate(equity)
    drawdown = equity - running_max
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    wins, losses = net_r[net_r > 0], net_r[net_r < 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else None
    total_return = float(equity[-1]) if len(equity) else 0.0
    return {"n_trades": int(len(net_r)), "total_return_R": round(total_return, 4),
           "expectancy_R": round(float(net_r.mean()), 5), "std_R": round(float(net_r.std(ddof=1)), 5)
           if len(net_r) > 1 else None,
           "hit_rate": round(float((net_r > 0).mean()), 4),
           "avg_win_R": round(float(wins.mean()), 5) if len(wins) else None,
           "avg_loss_R": round(float(losses.mean()), 5) if len(losses) else None,
           "profit_factor": round(pf, 4) if pf is not None else None,
           "max_drawdown_R": round(max_dd, 4),
           "return_over_drawdown": round(total_return / abs(max_dd), 4) if max_dd < -1e-9 else None}


# ==========================================================================
# primary experiment: ablation A0/A1/A2, walk-forward, per cost scenario
# ==========================================================================
def run_primary_experiment(cost_atr: float = COST_SCENARIOS["BASE"], target_col: str = "T2"
                           ) -> Dict[str, Any]:
    ds = build_pooled_dataset_90(PRIMARY_TF, _HORIZON)
    folds = p80.make_folds(ds, p80._FOLD_BOUNDARY_YEARS)
    vol_features = [f"feat__{c}" for c in BASELINE_B_COLUMNS]
    full_features = vol_features + ["feat__volume_rank"]

    per_fold = []
    for fold in folds:
        train, val, test, _ = p80.split_fold(ds, fold, PRIMARY_TF)
        if len(train) < 5000 or len(test) < _MIN_CELL_N:
            per_fold.append({"fold": fold.fold, "state": "INSUFFICIENT_SAMPLE"})
            continue
        a0 = _apply_risk_system(test, None, None, cost_atr)
        pred_a1 = _fit_predict_percentile(train, test, vol_features, target_col)
        a1 = _apply_risk_system(test, pred_a1["test_percentile"], pred_a1["eligibility_threshold"], cost_atr)
        pred_a2 = _fit_predict_percentile(train, test, full_features, target_col)
        a2 = _apply_risk_system(test, pred_a2["test_percentile"], pred_a2["eligibility_threshold"], cost_atr)

        m0, m1, m2 = _economic_metrics(a0["net_r_series"]), _economic_metrics(a1["net_r_series"]), \
                    _economic_metrics(a2["net_r_series"])
        per_fold.append({
            "fold": fold.fold, "test_start": fold.test_start.isoformat(), "test_end": fold.test_end.isoformat(),
            "n_test": len(test), "A0_baseline": m0, "A1_volatility_only": m1, "A2_plus_volume": m2,
            "A1_eligible": a1["n_eligible"], "A2_eligible": a2["n_eligible"],
            "delta_A2_minus_A1": {
                k: (round(m2[k] - m1[k], 5) if isinstance(m2.get(k), (int, float))
                   and isinstance(m1.get(k), (int, float)) else None)
                for k in ("expectancy_R", "max_drawdown_R", "return_over_drawdown", "std_R")},
        })
    return {"cost_atr": cost_atr, "per_fold": per_fold, "vol_features": vol_features}


def cost_sensitivity(target_col: str = "T2") -> Dict[str, Any]:
    return {name: run_primary_experiment(cost, target_col) for name, cost in COST_SCENARIOS.items()}


def break_even_cost(target_col: str = "T2", search_grid: Tuple[float, ...] = tuple(np.arange(0.0, 0.51, 0.01))
                    ) -> Dict[str, Any]:
    """Sweeps a predeclared cost grid to find the largest cost at which the
    pooled A2-vs-A1 expectancy advantage remains positive."""
    rows = []
    for c in search_grid:
        res = run_primary_experiment(float(c), target_col)
        deltas = [f["delta_A2_minus_A1"]["expectancy_R"] for f in res["per_fold"]
                 if "delta_A2_minus_A1" in f and f["delta_A2_minus_A1"]["expectancy_R"] is not None]
        pooled_delta = float(np.mean(deltas)) if deltas else None
        rows.append({"cost_atr": round(float(c), 3), "pooled_delta_expectancy_R": pooled_delta})
    positive = [r for r in rows if r["pooled_delta_expectancy_R"] is not None and r["pooled_delta_expectancy_R"] > 0]
    break_even = max((r["cost_atr"] for r in positive), default=None)
    return {"grid": rows, "break_even_cost_atr": break_even}


# ==========================================================================
# placebo -- shuffled volume_rank within the exact walk-forward apparatus
# ==========================================================================
def walk_forward_placebo(cost_atr: float = COST_SCENARIOS["BASE"], target_col: str = "T2",
                         seed: int = 90001) -> Dict[str, Any]:
    ds = build_pooled_dataset_90(PRIMARY_TF, _HORIZON)
    folds = p80.make_folds(ds, p80._FOLD_BOUNDARY_YEARS)
    vol_features = [f"feat__{c}" for c in BASELINE_B_COLUMNS]
    full_features = vol_features + ["feat__volume_rank"]
    rng = np.random.default_rng(seed)

    per_fold = []
    for fold in folds:
        train, val, test, _ = p80.split_fold(ds, fold, PRIMARY_TF)
        if len(train) < 5000 or len(test) < _MIN_CELL_N:
            per_fold.append({"fold": fold.fold, "state": "INSUFFICIENT_SAMPLE"})
            continue
        train_shuf, test_shuf = train.copy(), test.copy()
        train_shuf["feat__volume_rank"] = rng.permutation(train_shuf["feat__volume_rank"].to_numpy())
        test_shuf["feat__volume_rank"] = rng.permutation(test_shuf["feat__volume_rank"].to_numpy())
        pred_a1 = _fit_predict_percentile(train, test, vol_features, target_col)
        a1 = _apply_risk_system(test, pred_a1["test_percentile"], pred_a1["eligibility_threshold"], cost_atr)
        pred_a2_shuf = _fit_predict_percentile(train_shuf, test_shuf, full_features, target_col)
        a2_shuf = _apply_risk_system(test_shuf, pred_a2_shuf["test_percentile"],
                                     pred_a2_shuf["eligibility_threshold"], cost_atr)
        m1, m2s = _economic_metrics(a1["net_r_series"]), _economic_metrics(a2_shuf["net_r_series"])
        delta = (round(m2s["expectancy_R"] - m1["expectancy_R"], 5)
                if isinstance(m2s.get("expectancy_R"), (int, float))
                and isinstance(m1.get("expectancy_R"), (int, float)) else None)
        per_fold.append({"fold": fold.fold, "delta_expectancy_R": delta})
    valid = [f["delta_expectancy_R"] for f in per_fold if f.get("delta_expectancy_R") is not None]
    return {"per_fold": per_fold, "max_abs_delta": max((abs(d) for d in valid), default=None)}


# ==========================================================================
# cross-instrument / temporal / session breakdowns (diagnostics on the
# frozen primary experiment, at BASE cost, never re-tuned per cut)
# ==========================================================================
def cross_instrument_breakdown(target_col: str = "T2", cost_atr: float = COST_SCENARIOS["BASE"]
                               ) -> Dict[str, Any]:
    ds = build_pooled_dataset_90(PRIMARY_TF, _HORIZON)
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    vol_features = [f"feat__{c}" for c in BASELINE_B_COLUMNS]
    full_features = vol_features + ["feat__volume_rank"]
    pred_a1 = _fit_predict_percentile(disc, conf, vol_features, target_col)
    pred_a2 = _fit_predict_percentile(disc, conf, full_features, target_col)
    conf_reset = conf.reset_index(drop=True)
    out = {}
    for inst in INSTRUMENTS_83:
        mask = (conf_reset["instrument"] == inst).to_numpy()
        if mask.sum() < _MIN_CELL_N:
            out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        test_inst = conf_reset[mask]
        a1 = _apply_risk_system(test_inst, pred_a1["test_percentile"][mask], pred_a1["eligibility_threshold"], cost_atr)
        a2 = _apply_risk_system(test_inst, pred_a2["test_percentile"][mask], pred_a2["eligibility_threshold"], cost_atr)
        m1, m2 = _economic_metrics(a1["net_r_series"]), _economic_metrics(a2["net_r_series"])
        out[inst] = {"n": int(mask.sum()), "A1_expectancy_R": m1.get("expectancy_R"),
                    "A2_expectancy_R": m2.get("expectancy_R"),
                    "delta_expectancy_R": round((m2.get("expectancy_R") or 0) - (m1.get("expectancy_R") or 0), 5)}
    return out


def temporal_breakdown(target_col: str = "T2", cost_atr: float = COST_SCENARIOS["BASE"]) -> List[Dict[str, Any]]:
    result = run_primary_experiment(cost_atr, target_col)
    return [{"fold": f["fold"], "test_start": f.get("test_start"), "test_end": f.get("test_end"),
            "delta_expectancy_R": f.get("delta_A2_minus_A1", {}).get("expectancy_R")}
           for f in result["per_fold"] if "delta_A2_minus_A1" in f]


def session_breakdown(target_col: str = "T2", cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    ds = build_pooled_dataset_90(PRIMARY_TF, _HORIZON)
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    vol_features = [f"feat__{c}" for c in BASELINE_B_COLUMNS]
    full_features = vol_features + ["feat__volume_rank"]
    pred_a1 = _fit_predict_percentile(disc, conf, vol_features, target_col)
    pred_a2 = _fit_predict_percentile(disc, conf, full_features, target_col)
    conf_reset = conf.reset_index(drop=True)
    out = {}
    for sess in sorted(conf_reset["session"].dropna().unique().tolist()):
        mask = (conf_reset["session"] == sess).to_numpy()
        if mask.sum() < _MIN_CELL_N:
            out[str(sess)] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        test_sess = conf_reset[mask]
        a1 = _apply_risk_system(test_sess, pred_a1["test_percentile"][mask], pred_a1["eligibility_threshold"], cost_atr)
        a2 = _apply_risk_system(test_sess, pred_a2["test_percentile"][mask], pred_a2["eligibility_threshold"], cost_atr)
        m1, m2 = _economic_metrics(a1["net_r_series"]), _economic_metrics(a2["net_r_series"])
        out[str(sess)] = {"n": int(mask.sum()),
                         "delta_expectancy_R": round((m2.get("expectancy_R") or 0) - (m1.get("expectancy_R") or 0), 5)}
    return out


# ==========================================================================
# target-reachability economic test (reused directly from Phase 89's own
# construction, cited not rerun for the calibration numbers; here only the
# feasibility-filter economic consequence is newly evaluated)
# ==========================================================================
def target_reachability_economic_test(k_grid: Tuple[float, ...] = (0.5, 1.0, 1.5, 2.0),
                                      cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    ds = build_pooled_dataset_90(PRIMARY_TF, _HORIZON)
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    vol_features = [f"feat__{c}" for c in BASELINE_B_COLUMNS]
    full_features = vol_features + ["feat__volume_rank"]
    out = {}
    for k in k_grid:
        thr = k - 1.0
        ytr = (disc["T2"].to_numpy(float) >= thr).astype(int)
        yte = (conf["T2"].to_numpy(float) >= thr).astype(int)
        if len(set(ytr.tolist())) < 2:
            out[f"k_{k}"] = {"state": "DEGENERATE"}
            continue
        from sklearn.linear_model import LogisticRegression
        clf_b = Pipeline([("scale", StandardScaler()),
                          ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED))])
        clf_b.fit(disc[vol_features].to_numpy(float), ytr)
        p_b = clf_b.predict_proba(conf[vol_features].to_numpy(float))[:, 1]
        clf_c = Pipeline([("scale", StandardScaler()),
                          ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED))])
        clf_c.fit(disc[full_features].to_numpy(float), ytr)
        p_c = clf_c.predict_proba(conf[full_features].to_numpy(float))[:, 1]
        from sklearn.metrics import brier_score_loss
        out[f"k_{k}"] = {"n": len(yte), "baseline_B_brier": round(brier_score_loss(yte, p_b), 5),
                        "model_C_brier": round(brier_score_loss(yte, p_c), 5),
                        "brier_improvement": round(brier_score_loss(yte, p_b) - brier_score_loss(yte, p_c), 5)}
    return out


# ==========================================================================
# verdict classification
# ==========================================================================
_VALID_VERDICTS = ("RISK_MANAGEMENT_EDGE_CONFIRMED", "RISK_MANAGEMENT_EDGE_PROMISING",
                  "MAGNITUDE_SIGNAL_CONFIRMED_BUT_NOT_ECONOMICALLY_TRADABLE",
                  "MAGNITUDE_SIGNAL_INVALIDATED", "NO_MAGNITUDE_EDGE_FOUND")


def classify_verdict(cost_sens: Dict[str, Any], placebo: Dict[str, Any], cross_inst: Dict[str, Any],
                     break_even: Dict[str, Any]) -> Tuple[str, str]:
    def _pooled_delta(res: Dict[str, Any]) -> Optional[float]:
        deltas = [f["delta_A2_minus_A1"]["expectancy_R"] for f in res["per_fold"]
                 if "delta_A2_minus_A1" in f and f["delta_A2_minus_A1"]["expectancy_R"] is not None]
        return float(np.mean(deltas)) if deltas else None

    base_delta = _pooled_delta(cost_sens["BASE"])
    adverse_delta = _pooled_delta(cost_sens["ADVERSE"])
    severe_delta = _pooled_delta(cost_sens["SEVERE"])
    if base_delta is None:
        return "MAGNITUDE_SIGNAL_INVALIDATED", "Primary experiment could not be computed."

    max_placebo = placebo.get("max_abs_delta") or 0.0
    if abs(max_placebo) >= abs(base_delta) and base_delta != 0:
        return "MAGNITUDE_SIGNAL_INVALIDATED", \
            f"Placebo delta ({max_placebo}) is not clearly smaller than the real delta ({base_delta})."

    dd_deltas = [f["delta_A2_minus_A1"]["max_drawdown_R"] for f in cost_sens["BASE"]["per_fold"]
                if "delta_A2_minus_A1" in f and f["delta_A2_minus_A1"]["max_drawdown_R"] is not None]
    dd_improves = bool(dd_deltas) and (np.mean(dd_deltas) > 0)   # less-negative drawdown = improvement
    expectancy_improves_base = base_delta is not None and base_delta > 0

    if not (dd_improves or expectancy_improves_base):
        return "MAGNITUDE_SIGNAL_CONFIRMED_BUT_NOT_ECONOMICALLY_TRADABLE", \
            "Predictive/calibration value is real (Phase 89) but neither expectancy nor drawdown " \
            "improved under the primary risk-management experiment."

    n_pos_instruments = sum(1 for v in cross_inst.values()
                            if isinstance(v, dict) and (v.get("delta_expectancy_R") or 0) > 0)
    survives_adverse = adverse_delta is not None and (adverse_delta > 0 or (dd_improves))
    survives_severe = severe_delta is not None and (severe_delta > 0 or dd_improves)
    be_cost = break_even.get("break_even_cost_atr")
    be_survives_normal = be_cost is not None and be_cost >= COST_SCENARIOS["BASE"]

    if not be_survives_normal:
        return "RISK_MANAGEMENT_EDGE_PROMISING", \
            f"Improves risk-adjusted outcome at zero/low cost but the break-even cost " \
            f"({be_cost}) does not clearly clear the normal cost assumption " \
            f"({COST_SCENARIOS['BASE']})."
    if n_pos_instruments < 4 or not (survives_adverse and survives_severe):
        return "RISK_MANAGEMENT_EDGE_PROMISING", \
            f"Positive at normal costs and break-even clears the normal-cost bar, but breadth " \
            f"({n_pos_instruments}/{len(cross_inst)} instruments) or stress-cost survival is not yet sufficient."
    return "RISK_MANAGEMENT_EDGE_CONFIRMED", \
        "Improves risk-adjusted outcome beyond volatility-only risk management, survives placebo, " \
        f"clears break-even against normal cost, and generalizes across {n_pos_instruments}/{len(cross_inst)} instruments."


# ==========================================================================
# result container
# ==========================================================================
@dataclass
class Phase90Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    fixed_direction_note: str
    primary_experiment_base_cost: Dict[str, Any]
    cost_sensitivity: Dict[str, Any]
    break_even_cost: Dict[str, Any]
    walk_forward_placebo: Dict[str, Any]
    cross_instrument_breakdown: Dict[str, Any]
    temporal_breakdown: List[Dict[str, Any]]
    session_breakdown: Dict[str, Any]
    target_reachability_economic: Dict[str, Any]
    verdict: str
    verdict_reason: str
    directional_edge_found: bool
    magnitude_signal_found: bool
    risk_management_edge_found: bool
    profitable_trading_edge_found: str
    determinism: Dict[str, Any]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True
    strategy_status: str = "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def run() -> Phase90Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()

    primary_1 = run_primary_experiment(COST_SCENARIOS["BASE"])
    primary_2 = run_primary_experiment(COST_SCENARIOS["BASE"])
    determinism_match = (primary_1 == primary_2)

    cost_sens = cost_sensitivity()
    be = break_even_cost()
    placebo = walk_forward_placebo()
    cross_inst = cross_instrument_breakdown()
    temporal = temporal_breakdown()
    session = session_breakdown()
    reachability = target_reachability_economic_test()

    verdict, verdict_reason = classify_verdict(cost_sens, placebo, cross_inst, be)
    magnitude_signal_found = True     # established by Phase 89, re-affirmed unless invalidated here
    if verdict == "MAGNITUDE_SIGNAL_INVALIDATED":
        magnitude_signal_found = False
    risk_management_edge_found = verdict in ("RISK_MANAGEMENT_EDGE_CONFIRMED", "RISK_MANAGEMENT_EDGE_PROMISING")
    profitable_trading_edge_found = "NOT_ESTABLISHED"   # never claimed by this phase's design (Sec.41)

    ident = json.dumps({"schema": SCHEMA_VERSION, "verdict": verdict,
                       "base_cost_result": primary_1}, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase90Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(INSTRUMENTS_83), timeframe=PRIMARY_TF,
        fixed_direction_note="direction = +1 ('always long') for every opportunity, IDENTICAL between "
                            "BASELINE and MAGNITUDE-AWARE systems -- a documented non-signal scaffold, "
                            "not a directional claim (see module docstring).",
        primary_experiment_base_cost=primary_1, cost_sensitivity=cost_sens, break_even_cost=be,
        walk_forward_placebo=placebo, cross_instrument_breakdown=cross_inst, temporal_breakdown=temporal,
        session_breakdown=session, target_reachability_economic=reachability,
        verdict=verdict, verdict_reason=verdict_reason, directional_edge_found=False,
        magnitude_signal_found=magnitude_signal_found, risk_management_edge_found=risk_management_edge_found,
        profitable_trading_edge_found=profitable_trading_edge_found,
        determinism={"match": determinism_match}, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase90Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase90_magnitude_risk_management", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 90 - cost-aware magnitude risk-management validation ...", flush=True)
    res = run()
    print(f"\n=== PHASE 90 ({res.runtime_seconds}s) ===")
    print(f"\nPrimary experiment (BASE cost): {json.dumps(res.primary_experiment_base_cost, default=str)}")
    print(f"\nBreak-even cost: {json.dumps(res.break_even_cost, default=str)}")
    print(f"\nPlacebo: {json.dumps(res.walk_forward_placebo, default=str)}")
    print(f"\nCross-instrument: {json.dumps(res.cross_instrument_breakdown, default=str)}")
    print(f"\nSession: {json.dumps(res.session_breakdown, default=str)}")
    print(f"\nReachability economic: {json.dumps(res.target_reachability_economic, default=str)}")
    print(f"\nDeterminism: {res.determinism}")
    print(f"\nVERDICT: {res.verdict} -- {res.verdict_reason}")
    print(f"DIRECTIONAL_EDGE_FOUND={res.directional_edge_found}")
    print(f"MAGNITUDE_SIGNAL_FOUND={res.magnitude_signal_found}")
    print(f"RISK_MANAGEMENT_EDGE_FOUND={res.risk_management_edge_found}")
    print(f"PROFITABLE_TRADING_EDGE_FOUND={res.profitable_trading_edge_found}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "COST_SCENARIOS", "build_dataset_90", "build_pooled_dataset_90",
    "run_primary_experiment", "cost_sensitivity", "break_even_cost", "walk_forward_placebo",
    "cross_instrument_breakdown", "temporal_breakdown", "session_breakdown",
    "target_reachability_economic_test", "classify_verdict", "run", "persist", "get_result", "main",
]
