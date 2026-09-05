# -*- coding: utf-8 -*-
"""
Phase 92 -- Standalone Magnitude Eligibility Filter Validation.

Phase 90 found `RISK_MANAGEMENT_EDGE_PROMISING` from a combined treatment:
a volatility-targeting SIZING rule plus a bottom-quartile ELIGIBILITY
FILTER, both conditioned on a train-only-calibrated predicted-magnitude
percentile (Baseline-B volatility features + `volume_rank`). Phase 91
decomposed that combined treatment (on a single 70/30 split) and found
the eligibility filter, not the sizing rule, drives essentially all of
the pooled economic benefit -- sizing alone is actively harmful on 5 of
6 instruments. This phase does not reopen prediction (Layer 1, Phase 89:
CONFIRMED) or direction (still NOT FOUND) -- it isolates the filter as
its own standalone treatment, under GENUINE walk-forward (not a single
split), and subjects it to a battery of controls that Phase 91's own
decomposition never ran: randomized-retention and shuffled-filter
placebos, a deterministic generic exposure-reduction control, a
volatility-only-filter comparison (Baseline B alone, no volume_rank), a
directional-contamination classification, a direction-neutral
distributional check, and small predeclared threshold/target-horizon
neighborhoods.

Sizing is removed COMPLETELY in this phase (master prompt Sec.4). The
primary causal contrast is:

  BASELINE     -- unit exposure (size=1.0), every warmed-up opportunity
                  taken, direction FIXED = +1 ("always long", the same
                  documented non-signal scaffold as Phase 90/91 -- never
                  reused as a directional claim).
  FILTER-ONLY  -- unit exposure (size=1.0), IDENTICAL direction and
                  R-multiple construction, but observations failing the
                  frozen Phase-90 eligibility rule (predicted-magnitude
                  percentile below the 25th-percentile-of-TRAIN threshold)
                  are excluded. No sizing, no volatility scaling, no
                  leverage scaling, no exposure multiplier, no risk
                  targeting, no optimization anywhere in this comparison.

The frozen filter itself is reproduced EXACTLY from Phase 90's own code
(`phase90_magnitude_risk_management._fit_predict_percentile`, Ridge on
Baseline-B + volume_rank predicting T2, train-only percentile
calibration) -- never re-fit with new features, never re-optimized. Only
two small, PREDECLARED (before any result was seen) robustness
neighborhoods are tested after the primary result is locked: the
eligibility quantile (0.20/0.25/0.30, i.e. +/-0.05 around the frozen
0.25) and the target horizon (3/4/5 bars, i.e. +/-1 bar around the frozen
horizon=4) -- no broad search, no per-instrument tuning, no "best"
parameter is ever selected.

Reused, unchanged: Phase 83's frozen T1/T2 targets and 6-instrument
universe; Phase 84's frozen `volume_rank` construction; Phase 89's frozen
`BASELINE_B_COLUMNS`; Phase 90's frozen dataset builder, fixed-direction
scaffold, percentile predictor, and cost-scenario convention
(LOWER=0.025 reuses Phase 77's own precedented lower-cost point,
BASE/ADVERSE/SEVERE = 0.05/0.10/0.20 unchanged); Phase 80's frozen
walk-forward fold machinery. No new market data, no paid data, no new
directional signal, no live execution, no broker transmission, no
account-management mutation. The frozen Phase-74 Gold holdout is never
read -- `frozen_contract_hash` below cites the hard-coded canonical
constant (`gold_strategy_baseline.CANONICAL_CONTRACT_HASH`), never the
raw holdout trades themselves.
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

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase80_ml_volatility_regime as p80
import phase83_conditional_interaction_discovery as p83
import phase89_research_integrity_gate as p89
import phase90_magnitude_risk_management as p90
import phase91_magnitude_economic_attribution as p91
from phase83_conditional_interaction_discovery import INSTRUMENTS_83, PRIMARY_TF
from phase89_research_integrity_gate import BASELINE_B_COLUMNS
from phase90_magnitude_risk_management import COST_SCENARIOS, _HORIZON, _FIXED_DIRECTION, _ELIGIBILITY_QUANTILE

SCHEMA_VERSION = "phase92.1"
ARTIFACT_KEY = "phase92_standalone_filter_validation"

_MIN_CELL_N = 200
_LOWER_COST = 0.025    # precedented Phase 77 lower-cost scenario, reused not invented
_THRESHOLD_NEIGHBORHOOD: Tuple[float, ...] = (0.20, 0.25, 0.30)   # predeclared, +/-0.05 around frozen 0.25
_HORIZON_NEIGHBORHOOD: Tuple[int, ...] = (3, 4, 5)                # predeclared, +/-1 bar around frozen horizon=4
_RAND_PLACEBO_SEED = 92001
_SHUF_PLACEBO_SEED = 92501

# ==========================================================================
# Sec.1 -- design note: the exact frozen Phase-90 definitions this phase
# reproduces and never alters (auditable, testable, not just prose)
# ==========================================================================
DESIGN_NOTE: Dict[str, Any] = {
    "phase90_treatment_definition": "A2 = A1(volatility-only sizing+filter) + volume_rank (Ridge on "
                                    "Baseline-B + volume_rank predicting T2)",
    "phase90_sizing_transformation": "size = clip(1.5 - (1.5-0.5)*percentile, 0.5, 1.5) -- REMOVED "
                                     "COMPLETELY in Phase 92 (never imported, never applied)",
    "phase90_eligibility_filter": "eligible = test_percentile >= eligibility_threshold; "
                                  "eligibility_threshold = 25th-percentile of the TRAIN percentile "
                                  "distribution -- reproduced unchanged from phase90._fit_predict_percentile",
    "magnitude_variable": "T2 = forward true-range-sum / (atr_stable * horizon) - 1  (phase83._t2_range_ratio)",
    "volume_variable": "volume_rank = trailing 200-bar causal percentile rank of MT5 tick_volume "
                       "(phase84._add_volume_features)",
    "threshold": f"{_ELIGIBILITY_QUANTILE} quantile of the train-only calibrated percentile (frozen, Phase 90)",
    "target": "T2, via Pipeline(StandardScaler, Ridge(alpha=1.0)) on Baseline-B volatility features + volume_rank",
    "execution_convention": "direction FIXED = +1 ('always long', Phase90/91's documented non-signal "
                            "scaffold), R = direction*T1 - cost_atr, UNIT size (1.0) ONLY in Phase 92",
    "cost_model": "ATR round-trip proxy: LOWER=0.025 (Phase 77 precedent), BASE=0.05, ADVERSE=0.10, "
                 "SEVERE=0.20 (Phase 76/86 convention, reused unchanged)",
    "instruments": list(INSTRUMENTS_83),
    "timeframe": PRIMARY_TF,
    "walk_forward_folds": "Phase 80 expanding-window calendar-year folds, boundary years (2023,2024,2025), "
                          "purge + embargo, reused unchanged",
    "train_test_boundaries": "train = all data before boundary-year Jan 1; val = H1 of that year "
                             "(unused here); test = H2 of that year through (excl.) the next boundary year",
    "evaluation_metrics": "expectancy_R, total_return_R, hit_rate, profit_factor, max_drawdown_R, std_R, "
                          "median_R, downside_deviation, worst_R, p05_R, payoff_ratio, "
                          "drawdown_duration_bars",
    "artifact_paths": "reads phase89_research_integrity_gate / phase90_magnitude_risk_management / "
                      "phase91_magnitude_economic_attribution artifacts read-only (never recomputed); "
                      "persists its own phase92_standalone_filter_validation artifact",
}


# ==========================================================================
# core: reproduce the frozen filter exactly, per walk-forward fold
# ==========================================================================
def _fit_canonical_folds(horizon: int = _HORIZON, quantile: float = _ELIGIBILITY_QUANTILE,
                         use_volume: bool = True) -> List[Dict[str, Any]]:
    """One Ridge fit per fold on Baseline-B (+volume_rank if use_volume),
    predicting T2, train-only percentile calibration -- IDENTICAL machinery
    to Phase 90's own `_fit_predict_percentile`. Only the eligibility
    THRESHOLD is recomputed for an arbitrary quantile (cheap: it never
    requires refitting the model, since train_percentile/test_percentile
    do not depend on the quantile)."""
    ds = p90.build_pooled_dataset_90(PRIMARY_TF, horizon)
    folds = p80.make_folds(ds, p80._FOLD_BOUNDARY_YEARS)
    vol_features = [f"feat__{c}" for c in BASELINE_B_COLUMNS]
    features = vol_features + ["feat__volume_rank"] if use_volume else vol_features
    out = []
    for fold in folds:
        train, val, test, _ = p80.split_fold(ds, fold, PRIMARY_TF)
        if len(train) < 5000 or len(test) < _MIN_CELL_N:
            out.append({"fold": fold.fold, "state": "INSUFFICIENT_SAMPLE"})
            continue
        pred = p90._fit_predict_percentile(train, test, features, "T2")
        percentile = pred["test_percentile"]
        thr = float(np.percentile(pred["train_percentile"], quantile * 100))
        eligible = percentile >= thr
        out.append({"fold": fold.fold, "test_start": fold.test_start.isoformat(),
                   "test_end": fold.test_end.isoformat(), "test": test.reset_index(drop=True),
                   "percentile": percentile, "eligible": eligible, "threshold": thr})
    return out


def _apply_unit_exposure(t1: np.ndarray, eligible: np.ndarray, cost_atr: float) -> np.ndarray:
    """direction FIXED (+1), size FIXED (1.0) -- no sizing transformation
    exists anywhere in this function (Sec.4's critical rule)."""
    net_r = _FIXED_DIRECTION * t1 - cost_atr
    return net_r[eligible]


def _full_metrics(net_r: np.ndarray) -> Dict[str, Any]:
    """Extends Phase 90's `_economic_metrics` (mean/total/hit-rate/PF/
    drawdown) with Sec.6's additional risk metrics: median, downside
    deviation, worst observation, lower-tail quantile, payoff ratio,
    loss rate, drawdown duration."""
    base = p90._economic_metrics(net_r)
    if base.get("state") == "NO_TRADES":
        return base
    equity = np.cumsum(net_r)
    running_max = np.maximum.accumulate(equity)
    underwater = equity < running_max
    max_dur = cur = 0
    for u in underwater:
        cur = cur + 1 if u else 0
        max_dur = max(max_dur, cur)
    payoff = None
    if base.get("avg_win_R") is not None and base.get("avg_loss_R"):
        payoff = round(abs(base["avg_win_R"] / base["avg_loss_R"]), 4)
    base.update({
        "median_R": round(float(np.median(net_r)), 5),
        "loss_rate": round(float((net_r < 0).mean()), 4),
        "downside_deviation": round(float(np.sqrt(np.mean(np.minimum(net_r, 0.0) ** 2))), 5),
        "worst_R": round(float(net_r.min()), 5),
        "p05_R": round(float(np.percentile(net_r, 5)), 5),
        "payoff_ratio": payoff,
        "drawdown_duration_bars": int(max_dur),
    })
    return base


def _exposure_stats(test: pd.DataFrame, eligible: np.ndarray) -> Dict[str, Any]:
    n = len(test)
    n_ret = int(eligible.sum())
    t1, t2 = test["T1"].to_numpy(float), test["T2"].to_numpy(float)
    vr = test["feat__volume_rank"].to_numpy(float)

    def _m(arr: np.ndarray, mask: np.ndarray) -> Optional[float]:
        return round(float(arr[mask].mean()), 5) if mask.any() else None

    return {"n_total": n, "n_retained": n_ret, "retention_pct": round(n_ret / n, 4) if n else None,
           "exposure_reduction_pct": round(1 - n_ret / n, 4) if n else None,
           "mean_T2_retained": _m(t2, eligible), "mean_T2_removed": _m(t2, ~eligible),
           "mean_volume_rank_retained": _m(vr, eligible), "mean_volume_rank_removed": _m(vr, ~eligible),
           "mean_abs_T1_retained": _m(np.abs(t1), eligible), "mean_abs_T1_removed": _m(np.abs(t1), ~eligible),
           "mean_T1_retained": _m(t1, eligible), "mean_T1_removed": _m(t1, ~eligible)}


# ==========================================================================
# Sec.3-6 -- primary confirmatory experiment (frozen filter, unit exposure,
# genuine walk-forward, pooled + per-instrument + per-fold)
# ==========================================================================
def run_confirmatory_experiment(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    folds_data = _fit_canonical_folds()
    per_fold = []
    for fd in folds_data:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            per_fold.append(fd)
            continue
        test, eligible = fd["test"], fd["eligible"]
        t1 = test["T1"].to_numpy(float)
        baseline_net = _apply_unit_exposure(t1, np.ones(len(test), dtype=bool), cost_atr)
        filter_net = _apply_unit_exposure(t1, eligible, cost_atr)
        m_base, m_filt = _full_metrics(baseline_net), _full_metrics(filter_net)
        exposure = _exposure_stats(test, eligible)
        per_inst: Dict[str, Any] = {}
        for inst in INSTRUMENTS_83:
            mask = (test["instrument"] == inst).to_numpy()
            if mask.sum() < _MIN_CELL_N:
                per_inst[inst] = {"state": "INSUFFICIENT_SAMPLE"}
                continue
            b = _apply_unit_exposure(t1[mask], np.ones(int(mask.sum()), dtype=bool), cost_atr)
            f = _apply_unit_exposure(t1[mask], eligible[mask], cost_atr)
            mb, mf = _full_metrics(b), _full_metrics(f)
            per_inst[inst] = {"baseline": mb, "filter": mf,
                             "delta_expectancy_R": round((mf.get("expectancy_R") or 0) - (mb.get("expectancy_R") or 0), 5),
                             "delta_max_drawdown_R": round((mf.get("max_drawdown_R") or 0) - (mb.get("max_drawdown_R") or 0), 5)}
        per_fold.append({"fold": fd["fold"], "test_start": fd["test_start"], "test_end": fd["test_end"],
                        "n_test": len(test), "baseline": m_base, "filter": m_filt, "exposure": exposure,
                        "delta_expectancy_R": round((m_filt.get("expectancy_R") or 0) - (m_base.get("expectancy_R") or 0), 5),
                        "delta_max_drawdown_R": round((m_filt.get("max_drawdown_R") or 0) - (m_base.get("max_drawdown_R") or 0), 5),
                        "per_instrument": per_inst})
    return {"cost_atr": cost_atr, "per_fold": per_fold}


# ==========================================================================
# Sec.7/8 -- removed vs retained observation-level attribution
# ==========================================================================
def removed_vs_retained_analysis(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    folds_data = _fit_canonical_folds()

    def _empty_acc() -> Dict[str, list]:
        return {"t1_r": [], "t1_ret": [], "t2_r": [], "t2_ret": [], "vr_r": [], "vr_ret": []}

    pooled_acc = _empty_acc()
    per_inst_acc = {inst: _empty_acc() for inst in INSTRUMENTS_83}
    for fd in folds_data:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        test, eligible = fd["test"], fd["eligible"]
        removed = ~eligible
        t1, t2, vr = test["T1"].to_numpy(float), test["T2"].to_numpy(float), test["feat__volume_rank"].to_numpy(float)
        pooled_acc["t1_r"].append(t1[removed]); pooled_acc["t1_ret"].append(t1[eligible])
        pooled_acc["t2_r"].append(t2[removed]); pooled_acc["t2_ret"].append(t2[eligible])
        pooled_acc["vr_r"].append(vr[removed]); pooled_acc["vr_ret"].append(vr[eligible])
        inst_col = test["instrument"].to_numpy()
        for inst in INSTRUMENTS_83:
            mask = inst_col == inst
            per_inst_acc[inst]["t1_r"].append(t1[mask & removed]); per_inst_acc[inst]["t1_ret"].append(t1[mask & eligible])
            per_inst_acc[inst]["t2_r"].append(t2[mask & removed]); per_inst_acc[inst]["t2_ret"].append(t2[mask & eligible])
            per_inst_acc[inst]["vr_r"].append(vr[mask & removed]); per_inst_acc[inst]["vr_ret"].append(vr[mask & eligible])

    def _cat(lst: list) -> np.ndarray:
        arrs = [a for a in lst if len(a)]
        return np.concatenate(arrs) if arrs else np.array([])

    def _pair_stats(removed_arr: np.ndarray, retained_arr: np.ndarray) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if len(removed_arr):
            out["mean_removed"] = round(float(removed_arr.mean()), 5)
            out["median_removed"] = round(float(np.median(removed_arr)), 5)
        if len(retained_arr):
            out["mean_retained"] = round(float(retained_arr.mean()), 5)
            out["median_retained"] = round(float(np.median(retained_arr)), 5)
        return out

    def _bundle(acc: Dict[str, list]) -> Dict[str, Any]:
        t1_r, t1_ret = _cat(acc["t1_r"]), _cat(acc["t1_ret"])
        bundle = {"T1": _pair_stats(t1_r, t1_ret), "T2": _pair_stats(_cat(acc["t2_r"]), _cat(acc["t2_ret"])),
                 "volume_rank": _pair_stats(_cat(acc["vr_r"]), _cat(acc["vr_ret"])),
                 "gross_return_removed": round(float(t1_r.mean()), 5) if len(t1_r) else None,
                 "net_return_removed": round(float(t1_r.mean() - cost_atr), 5) if len(t1_r) else None,
                 "gross_return_retained": round(float(t1_ret.mean()), 5) if len(t1_ret) else None,
                 "net_return_retained": round(float(t1_ret.mean() - cost_atr), 5) if len(t1_ret) else None,
                 "adverse_tail_frequency_removed": round(float((t1_r < 0).mean()), 4) if len(t1_r) else None,
                 "positive_tail_frequency_removed": round(float((t1_r > 0).mean()), 4) if len(t1_r) else None}
        bundle["removed_worse_than_retained"] = (bundle["T1"].get("mean_removed") is not None
                                                and bundle["T1"].get("mean_retained") is not None
                                                and bundle["T1"]["mean_removed"] < bundle["T1"]["mean_retained"])
        return bundle

    return {"pooled": _bundle(pooled_acc), "per_instrument": {inst: _bundle(acc) for inst, acc in per_inst_acc.items()}}


# ==========================================================================
# Sec.9 -- randomized retention placebo (fresh random k-of-n draw)
# ==========================================================================
def randomized_retention_placebo(n_reps: int = 500, seed: int = _RAND_PLACEBO_SEED,
                                 cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    folds_data = _fit_canonical_folds()
    rng = np.random.default_rng(seed)
    pooled_real, pooled_placebo = [], []
    per_instrument: Dict[str, Dict[str, list]] = {inst: {"real": [], "placebo": []} for inst in INSTRUMENTS_83}
    for fd in folds_data:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        test, eligible = fd["test"], fd["eligible"]
        t1 = test["T1"].to_numpy(float)
        n, k = len(t1), int(eligible.sum())
        pooled_real.append((t1 - cost_atr)[eligible])
        for _ in range(n_reps):
            idx = rng.choice(n, size=k, replace=False)
            pooled_placebo.append(float((t1[idx] - cost_atr).mean()))
        inst_col = test["instrument"].to_numpy()
        for inst in INSTRUMENTS_83:
            mask = inst_col == inst
            t1_i, elig_i = t1[mask], eligible[mask]
            n_i, k_i = len(t1_i), int(elig_i.sum())
            if n_i < _MIN_CELL_N or k_i == 0:
                continue
            per_instrument[inst]["real"].append(float((t1_i[elig_i] - cost_atr).mean()))
            for _ in range(n_reps):
                idx_i = rng.choice(n_i, size=k_i, replace=False)
                per_instrument[inst]["placebo"].append(float((t1_i[idx_i] - cost_atr).mean()))

    pooled_out = None
    if pooled_real and pooled_placebo:
        real_mean = float(np.concatenate(pooled_real).mean())
        parr = np.array(pooled_placebo)
        pstd = float(parr.std(ddof=1))
        pooled_out = {"real_expectancy_R": round(real_mean, 5), "placebo_mean": round(float(parr.mean()), 5),
                     "placebo_std": round(pstd, 5), "percentile_of_real": round(float((parr <= real_mean).mean()), 4),
                     "empirical_p_one_sided": round(float((parr >= real_mean).mean()), 4),
                     "effect_size_ratio": round((real_mean - float(parr.mean())) / pstd, 4) if pstd > 0 else None,
                     "n_reps_total": len(parr)}
    per_inst_out = {}
    for inst, d in per_instrument.items():
        if not d["real"] or not d["placebo"]:
            per_inst_out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        real_mean = float(np.mean(d["real"]))
        parr = np.array(d["placebo"])
        per_inst_out[inst] = {"real_expectancy_R": round(real_mean, 5), "placebo_mean": round(float(parr.mean()), 5),
                             "placebo_std": round(float(parr.std(ddof=1)), 5),
                             "percentile_of_real": round(float((parr <= real_mean).mean()), 4),
                             "empirical_p_one_sided": round(float((parr >= real_mean).mean()), 4)}
    return {"pooled": pooled_out, "per_instrument": per_inst_out, "n_reps": n_reps, "seed": seed}


# ==========================================================================
# Sec.10 -- shuffled-filter placebo (permutes the REAL eligibility array)
# ==========================================================================
def shuffled_filter_placebo(n_reps: int = 200, seed: int = _SHUF_PLACEBO_SEED,
                            cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    folds_data = _fit_canonical_folds()
    rng = np.random.default_rng(seed)
    pooled_real, pooled_placebo = [], []
    for fd in folds_data:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        test, eligible = fd["test"], fd["eligible"]
        t1 = test["T1"].to_numpy(float)
        pooled_real.append((t1 - cost_atr)[eligible])
        for _ in range(n_reps):
            shuf = rng.permutation(eligible)
            pooled_placebo.append(float((t1[shuf] - cost_atr).mean()))
    out = None
    if pooled_real and pooled_placebo:
        real_mean = float(np.concatenate(pooled_real).mean())
        parr = np.array(pooled_placebo)
        out = {"real_expectancy_R": round(real_mean, 5), "placebo_mean": round(float(parr.mean()), 5),
              "placebo_std": round(float(parr.std(ddof=1)), 5),
              "percentile_of_real": round(float((parr <= real_mean).mean()), 4),
              "empirical_p_one_sided": round(float((parr >= real_mean).mean()), 4), "n_reps_total": len(parr)}
    return {"pooled": out, "n_reps": n_reps, "seed": seed,
           "note": "Permutes the REAL eligibility boolean array itself (a uniform random k-of-n subset by "
                   "construction) rather than drawing a fresh random index set (Sec.9's mechanism). This is "
                   "an independently-implemented control as the master prompt requires, but it targets the "
                   "SAME null (Null 1: the filter is equivalent to random exposure reduction) as the "
                   "randomized-retention placebo and is mathematically expected to -- and does -- agree "
                   "closely with it; it is not independent evidence beyond Sec.9's own result."}


# ==========================================================================
# Sec.20 -- deterministic generic exposure-reduction control (return-
# independent systematic sampling, matched to the real retention fraction)
# ==========================================================================
def exposure_reduction_control(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    folds_data = _fit_canonical_folds()
    pooled = {"base": [], "generic": [], "filter": []}
    per_instrument: Dict[str, Dict[str, list]] = {inst: {"base": [], "generic": [], "filter": []} for inst in INSTRUMENTS_83}
    for fd in folds_data:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        test, eligible = fd["test"], fd["eligible"]
        t1 = test["T1"].to_numpy(float)
        n, k = len(t1), int(eligible.sum())
        retention_frac = k / n if n else 0.0
        drop_frac = 1.0 - retention_frac
        generic_mask = np.ones(n, dtype=bool)
        if 0.0 < drop_frac < 1.0:
            stride = max(int(round(1.0 / drop_frac)), 2)
            generic_mask[::stride] = False   # deterministic, positional, never uses T1/T2/volume_rank
        pooled["base"].append(t1 - cost_atr)
        pooled["generic"].append((t1 - cost_atr)[generic_mask])
        pooled["filter"].append((t1 - cost_atr)[eligible])
        inst_col = test["instrument"].to_numpy()
        for inst in INSTRUMENTS_83:
            mask = inst_col == inst
            if mask.sum() < _MIN_CELL_N:
                continue
            per_instrument[inst]["base"].append(t1[mask] - cost_atr)
            per_instrument[inst]["generic"].append((t1[mask] - cost_atr)[generic_mask[mask]])
            per_instrument[inst]["filter"].append((t1[mask] - cost_atr)[eligible[mask]])
    pooled_out = {"baseline": _full_metrics(np.concatenate(pooled["base"])),
                 "generic_exposure_reduction": _full_metrics(np.concatenate(pooled["generic"])),
                 "real_filter": _full_metrics(np.concatenate(pooled["filter"]))}
    per_inst_out = {}
    for inst, d in per_instrument.items():
        if not d["base"]:
            per_inst_out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        per_inst_out[inst] = {"baseline": _full_metrics(np.concatenate(d["base"])),
                             "generic_exposure_reduction": _full_metrics(np.concatenate(d["generic"])),
                             "real_filter": _full_metrics(np.concatenate(d["filter"]))}
    return {"pooled": pooled_out, "per_instrument": per_inst_out}


# ==========================================================================
# Sec.11 -- directional-contamination classification
# ==========================================================================
def directional_contamination_test(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    folds_data = _fit_canonical_folds()
    acc = {inst: {"t1": [], "t2": [], "t1_removed": [], "t1_retained": []} for inst in INSTRUMENTS_83}
    for fd in folds_data:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        test, eligible = fd["test"], fd["eligible"]
        t1, t2 = test["T1"].to_numpy(float), test["T2"].to_numpy(float)
        inst_col = test["instrument"].to_numpy()
        for inst in INSTRUMENTS_83:
            mask = inst_col == inst
            acc[inst]["t1"].append(t1[mask]); acc[inst]["t2"].append(t2[mask])
            acc[inst]["t1_removed"].append(t1[mask & ~eligible]); acc[inst]["t1_retained"].append(t1[mask & eligible])

    out: Dict[str, Any] = {}
    for inst in INSTRUMENTS_83:
        t1_all = np.concatenate(acc[inst]["t1"]) if acc[inst]["t1"] else np.array([])
        t2_all = np.concatenate(acc[inst]["t2"]) if acc[inst]["t2"] else np.array([])
        removed = np.concatenate(acc[inst]["t1_removed"]) if acc[inst]["t1_removed"] else np.array([])
        retained = np.concatenate(acc[inst]["t1_retained"]) if acc[inst]["t1_retained"] else np.array([])
        if len(t1_all) < 2 or len(removed) == 0:
            out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        corr_t1_t2 = float(np.corrcoef(t1_all, t2_all)[0, 1])
        mean_t1_removed = float(removed.mean())
        mean_t1_retained = float(retained.mean()) if len(retained) else None
        mean_abs_removed = float(np.abs(removed).mean())
        mean_abs_retained = float(np.abs(retained).mean()) if len(retained) else None
        if abs(corr_t1_t2) < 0.05:
            case = "Case D" if (mean_t1_retained is None or mean_t1_removed >= mean_t1_retained) else "Case A"
        elif corr_t1_t2 < -0.05 and mean_t1_removed < 0:
            case = "Case B"
        elif mean_abs_retained is not None and mean_abs_removed > mean_abs_retained * 1.05 \
                and abs(mean_t1_removed) < 0.3 * mean_abs_removed:
            case = "Case C"
        else:
            case = "Case A"
        out[inst] = {"corr_T1_T2": round(corr_t1_t2, 4), "mean_T1_removed": round(mean_t1_removed, 5),
                    "mean_T1_retained": round(mean_t1_retained, 5) if mean_t1_retained is not None else None,
                    "mean_abs_T1_removed": round(mean_abs_removed, 5),
                    "mean_abs_T1_retained": round(mean_abs_retained, 5) if mean_abs_retained is not None else None,
                    "frac_positive_removed": round(float((removed > 0).mean()), 4),
                    "frac_negative_removed": round(float((removed < 0).mean()), 4), "case": case}
    out["_note"] = ("Case classification is a descriptive heuristic (|corr(T1,T2)|>=0.05 threshold, sign of "
                    "mean_T1_removed, relative magnitude of mean_abs_T1) applied IDENTICALLY to every "
                    "instrument, not a formal statistical test. Case B ('the filter merely removes adverse "
                    "directional observations from an always-long scaffold') must NOT be read as a "
                    "universal risk-management edge -- see the report's Limitations section.")
    return out


# ==========================================================================
# Sec.12 -- direction-neutral distributional control (deliberately NOT a
# synthetic sign-neutral P&L construction -- see Phase 89's own precedent)
# ==========================================================================
def direction_neutral_control() -> Dict[str, Any]:
    folds_data = _fit_canonical_folds()
    acc = {inst: {"abs_all": [], "abs_ret": [], "t2_all": [], "t2_ret": []} for inst in INSTRUMENTS_83}
    for fd in folds_data:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        test, eligible = fd["test"], fd["eligible"]
        t1, t2 = test["T1"].to_numpy(float), test["T2"].to_numpy(float)
        inst_col = test["instrument"].to_numpy()
        for inst in INSTRUMENTS_83:
            mask = inst_col == inst
            acc[inst]["abs_all"].append(np.abs(t1[mask])); acc[inst]["abs_ret"].append(np.abs(t1[mask & eligible]))
            acc[inst]["t2_all"].append(t2[mask]); acc[inst]["t2_ret"].append(t2[mask & eligible])
    out: Dict[str, Any] = {}
    for inst in INSTRUMENTS_83:
        a_all = np.concatenate(acc[inst]["abs_all"]) if acc[inst]["abs_all"] else np.array([])
        a_ret = np.concatenate(acc[inst]["abs_ret"]) if acc[inst]["abs_ret"] else np.array([])
        t2_all = np.concatenate(acc[inst]["t2_all"]) if acc[inst]["t2_all"] else np.array([])
        t2_ret = np.concatenate(acc[inst]["t2_ret"]) if acc[inst]["t2_ret"] else np.array([])
        if len(a_all) == 0:
            out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        out[inst] = {"mean_abs_T1_all": round(float(a_all.mean()), 5),
                    "mean_abs_T1_retained": round(float(a_ret.mean()), 5) if len(a_ret) else None,
                    "p95_abs_T1_all": round(float(np.percentile(a_all, 95)), 5),
                    "p95_abs_T1_retained": round(float(np.percentile(a_ret, 95)), 5) if len(a_ret) else None,
                    "mean_T2_all": round(float(t2_all.mean()), 5),
                    "mean_T2_retained": round(float(t2_ret.mean()), 5) if len(t2_ret) else None}
    out["_note"] = ("A direction-neutral DIAGNOSTIC only (distributional comparison of absolute movement "
                    "and forward magnitude, retained vs full population) -- deliberately NOT a synthetic "
                    "sign-neutral P&L construction, following Phase 89's own precedent that such a "
                    "construction would prove nothing under a direction-uninformative process and risks "
                    "reading as a disguised directional strategy.")
    return out


# ==========================================================================
# Sec.19 -- volatility-confound test: volume-informed filter vs an
# identically-constructed volatility-ONLY filter (Baseline B alone)
# ==========================================================================
def volatility_confound_test(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    folds_vol = _fit_canonical_folds(use_volume=False)
    folds_full = _fit_canonical_folds(use_volume=True)
    pooled = {"base": [], "vol_only": [], "full": []}
    per_instrument: Dict[str, Dict[str, list]] = {inst: {"base": [], "vol_only": [], "full": []} for inst in INSTRUMENTS_83}
    for fv, ff in zip(folds_vol, folds_full):
        if fv.get("state") == "INSUFFICIENT_SAMPLE" or ff.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        test = fv["test"]
        t1 = test["T1"].to_numpy(float)
        pooled["base"].append(t1 - cost_atr)
        pooled["vol_only"].append((t1 - cost_atr)[fv["eligible"]])
        pooled["full"].append((t1 - cost_atr)[ff["eligible"]])
        inst_col = test["instrument"].to_numpy()
        for inst in INSTRUMENTS_83:
            mask = inst_col == inst
            if mask.sum() < _MIN_CELL_N:
                continue
            per_instrument[inst]["base"].append(t1[mask] - cost_atr)
            per_instrument[inst]["vol_only"].append((t1[mask] - cost_atr)[fv["eligible"][mask]])
            per_instrument[inst]["full"].append((t1[mask] - cost_atr)[ff["eligible"][mask]])
    pooled_out = {"baseline": _full_metrics(np.concatenate(pooled["base"])),
                 "volatility_only_filter": _full_metrics(np.concatenate(pooled["vol_only"])),
                 "volume_informed_filter": _full_metrics(np.concatenate(pooled["full"]))}
    per_inst_out, classification = {}, {}
    for inst, d in per_instrument.items():
        if not d["base"]:
            per_inst_out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
            classification[inst] = "INSUFFICIENT_EVIDENCE"
            continue
        mb = _full_metrics(np.concatenate(d["base"]))
        mv = _full_metrics(np.concatenate(d["vol_only"]))
        mf = _full_metrics(np.concatenate(d["full"]))
        per_inst_out[inst] = {"baseline": mb, "volatility_only_filter": mv, "volume_informed_filter": mf}
        d_vol = (mv.get("expectancy_R") or 0) - (mb.get("expectancy_R") or 0)
        d_full = (mf.get("expectancy_R") or 0) - (mb.get("expectancy_R") or 0)
        if d_full > d_vol + 0.002:
            classification[inst] = "INDEPENDENT_FILTER_INFORMATION"
        elif abs(d_full - d_vol) <= 0.002:
            classification[inst] = "MOSTLY_VOLATILITY_PROXY" if d_vol > 0 else "INDISTINGUISHABLE_FROM_VOLATILITY_REDUCTION"
        else:
            classification[inst] = "INSUFFICIENT_EVIDENCE"
    return {"pooled": pooled_out, "per_instrument": per_inst_out, "classification": classification,
           "note": "Compares the frozen volume-informed filter (Baseline B + volume_rank) against an "
                   "identically-constructed volatility-ONLY filter (Baseline B alone, Phase 89's own "
                   "BASELINE_B_COLUMNS) -- same architecture, same quantile rule; the ONLY difference is "
                   "whether volume_rank is in the model. This isolates whether the filter's information is "
                   "specific to tick volume or merely a restatement of ordinary volatility."}


# ==========================================================================
# Sec.13 -- threshold-neighborhood robustness (predeclared, no search)
# ==========================================================================
def threshold_robustness(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    by_quantile: Dict[str, Any] = {}
    for q in _THRESHOLD_NEIGHBORHOOD:
        folds_data = _fit_canonical_folds(quantile=q)
        pooled_base, pooled_filt = [], []
        inst_deltas: Dict[str, list] = {}
        fold_signs = []
        for fd in folds_data:
            if fd.get("state") == "INSUFFICIENT_SAMPLE":
                continue
            test, eligible = fd["test"], fd["eligible"]
            t1 = test["T1"].to_numpy(float)
            b, f = t1 - cost_atr, (t1 - cost_atr)[eligible]
            pooled_base.append(b); pooled_filt.append(f)
            fold_signs.append(int(np.sign(f.mean() - b.mean())))
            inst_col = test["instrument"].to_numpy()
            for inst in INSTRUMENTS_83:
                mask = inst_col == inst
                if mask.sum() < _MIN_CELL_N:
                    continue
                d = float((t1[mask] - cost_atr)[eligible[mask]].mean() - (t1[mask] - cost_atr).mean())
                inst_deltas.setdefault(inst, []).append(d)
        mb, mf = _full_metrics(np.concatenate(pooled_base)), _full_metrics(np.concatenate(pooled_filt))
        pooled_delta = (mf.get("expectancy_R") or 0) - (mb.get("expectancy_R") or 0)
        by_quantile[f"q_{q:.2f}"] = {"quantile": q, "pooled_delta_expectancy_R": round(pooled_delta, 5),
                                    "pooled_delta_max_drawdown_R": round((mf.get("max_drawdown_R") or 0) - (mb.get("max_drawdown_R") or 0), 5),
                                    "fold_signs": fold_signs,
                                    "instrument_signs": {k: int(np.sign(np.mean(v))) for k, v in inst_deltas.items()}}
    pooled_signs = {int(np.sign(v["pooled_delta_expectancy_R"])) for v in by_quantile.values()}
    pooled_sign_stable = len(pooled_signs) <= 1
    inst_stable = 0
    for inst in INSTRUMENTS_83:
        signs = {by_quantile[f"q_{q:.2f}"]["instrument_signs"].get(inst, 0) for q in _THRESHOLD_NEIGHBORHOOD}
        if len(signs) <= 1:
            inst_stable += 1
    if pooled_sign_stable and inst_stable >= 5:
        classification = "ROBUST"
    elif pooled_sign_stable and inst_stable >= 3:
        classification = "MODERATELY_SENSITIVE"
    else:
        classification = "HIGHLY_THRESHOLD_SENSITIVE"
    return {"by_quantile": by_quantile, "pooled_sign_stable": pooled_sign_stable,
           "n_instruments_sign_stable": inst_stable, "classification": classification}


# ==========================================================================
# Sec.14 -- magnitude-target (horizon) neighborhood robustness
# ==========================================================================
def magnitude_target_robustness(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    by_horizon: Dict[str, Any] = {}
    for h in _HORIZON_NEIGHBORHOOD:
        folds_data = _fit_canonical_folds(horizon=h)
        pooled_base, pooled_filt = [], []
        inst_deltas: Dict[str, list] = {}
        for fd in folds_data:
            if fd.get("state") == "INSUFFICIENT_SAMPLE":
                continue
            test, eligible = fd["test"], fd["eligible"]
            t1 = test["T1"].to_numpy(float)
            pooled_base.append(t1 - cost_atr); pooled_filt.append((t1 - cost_atr)[eligible])
            inst_col = test["instrument"].to_numpy()
            for inst in INSTRUMENTS_83:
                mask = inst_col == inst
                if mask.sum() < _MIN_CELL_N:
                    continue
                d = float((t1[mask] - cost_atr)[eligible[mask]].mean() - (t1[mask] - cost_atr).mean())
                inst_deltas.setdefault(inst, []).append(d)
        mb, mf = _full_metrics(np.concatenate(pooled_base)), _full_metrics(np.concatenate(pooled_filt))
        pooled_delta = (mf.get("expectancy_R") or 0) - (mb.get("expectancy_R") or 0)
        by_horizon[f"h_{h}"] = {"horizon": h, "pooled_delta_expectancy_R": round(pooled_delta, 5),
                               "instrument_signs": {k: int(np.sign(np.mean(v))) for k, v in inst_deltas.items()}}
    signs = {int(np.sign(v["pooled_delta_expectancy_R"])) for v in by_horizon.values()}
    pooled_sign_stable = len(signs) <= 1
    classification = "ROBUST" if pooled_sign_stable else "HIGHLY_TARGET_SENSITIVE"
    return {"by_horizon": by_horizon, "pooled_sign_stable": pooled_sign_stable, "classification": classification}


# ==========================================================================
# Sec.21 -- cost robustness (LOWER/BASE/ADVERSE/SEVERE, no optimization)
# ==========================================================================
def cost_robustness() -> Dict[str, Any]:
    grid = {"LOWER": _LOWER_COST, **COST_SCENARIOS}
    by_cost = {}
    for name, c in grid.items():
        exp = run_confirmatory_experiment(c)
        deltas = [f["delta_expectancy_R"] for f in exp["per_fold"] if "delta_expectancy_R" in f]
        by_cost[name] = {"cost_atr": c, "pooled_delta_expectancy_R": round(float(np.mean(deltas)), 5) if deltas else None,
                        "fold_deltas": deltas}
    signs = [int(np.sign(v["pooled_delta_expectancy_R"])) for v in by_cost.values() if v["pooled_delta_expectancy_R"] is not None]
    all_same_sign = len(set(signs)) <= 1 if signs else False
    if all_same_sign and signs and signs[0] > 0:
        classification = "COST_INDEPENDENT"
    elif all_same_sign:
        classification = "COST_DEPENDENT"
    else:
        classification = "COST_SENSITIVE"
    return {"by_cost": by_cost, "classification": classification}


# ==========================================================================
# Sec.22 -- drawdown attribution (selection vs generic exposure reduction)
# ==========================================================================
def drawdown_attribution(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    er = exposure_reduction_control(cost_atr)
    base_dd = er["pooled"]["baseline"].get("max_drawdown_R")
    generic_dd = er["pooled"]["generic_exposure_reduction"].get("max_drawdown_R")
    filter_dd = er["pooled"]["real_filter"].get("max_drawdown_R")
    generic_improve = (generic_dd - base_dd) if (generic_dd is not None and base_dd is not None) else None
    filter_improve = (filter_dd - base_dd) if (filter_dd is not None and base_dd is not None) else None
    incremental = (filter_improve - generic_improve) if (generic_improve is not None and filter_improve is not None) else None
    return {"baseline_max_drawdown_R": base_dd, "generic_reduction_max_drawdown_R": generic_dd,
           "real_filter_max_drawdown_R": filter_dd,
           "generic_improvement_R": round(generic_improve, 4) if generic_improve is not None else None,
           "filter_improvement_R": round(filter_improve, 4) if filter_improve is not None else None,
           "incremental_improvement_beyond_generic_R": round(incremental, 4) if incremental is not None else None,
           "interpretation": "incremental_improvement_beyond_generic_R > 0 means the real filter's drawdown "
                             "reduction exceeds what merely trading less (same retention %, a deterministic, "
                             "return-independent selection) would achieve on its own -- i.e. selection, not "
                             "just reduced exposure, is doing the work."}


# ==========================================================================
# Sec.17 -- fold-level consistency classification
# ==========================================================================
def fold_level_classification(exp_result: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for inst in INSTRUMENTS_83:
        deltas = [f["per_instrument"][inst]["delta_expectancy_R"] for f in exp_result["per_fold"]
                 if "per_instrument" in f and "delta_expectancy_R" in f["per_instrument"].get(inst, {})]
        if not deltas:
            out[inst] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        signs = [np.sign(d) for d in deltas]
        n_pos = sum(1 for d in deltas if d > 0)
        if len(set(signs)) <= 1 and signs[0] > 0 and abs(float(np.mean(deltas))) > 0.001:
            cls = "STRONG_CONSISTENCY"
        elif n_pos >= (len(deltas) + 1) // 2 and float(np.mean(deltas)) > 0:
            cls = "MODERATE_CONSISTENCY"
        elif len(set(signs)) > 1:
            cls = "MIXED"
        else:
            cls = "FAILURE"
        out[inst] = {"fold_deltas": deltas, "n_positive": n_pos, "n_folds": len(deltas), "classification": cls}
    return out


# ==========================================================================
# Sec.16 -- quote-currency hypothesis (descriptive only, N=6)
# ==========================================================================
def quote_currency_hypothesis_test(exp_result: Dict[str, Any], directional: Dict[str, Any]) -> Dict[str, Any]:
    jpy, other = p91._POSITIVE_GROUP, p91._NEGATIVE_GROUP   # identical to the JPY-quoted split

    def _group_mean_delta(group: Tuple[str, ...]) -> Optional[float]:
        vals = [f["per_instrument"][i]["delta_expectancy_R"] for f in exp_result["per_fold"]
               if "per_instrument" in f for i in group if "delta_expectancy_R" in f["per_instrument"].get(i, {})]
        return float(np.mean(vals)) if vals else None

    def _group_mean_corr(group: Tuple[str, ...]) -> Optional[float]:
        vals = [directional[i]["corr_T1_T2"] for i in group if i in directional and "corr_T1_T2" in directional[i]]
        return float(np.mean(vals)) if vals else None

    jpy_delta, other_delta = _group_mean_delta(jpy), _group_mean_delta(other)
    jpy_corr, other_corr = _group_mean_corr(jpy), _group_mean_corr(other)
    return {"jpy_quoted_group": list(jpy), "non_jpy_group": list(other),
           "jpy_mean_filter_effect": round(jpy_delta, 5) if jpy_delta is not None else None,
           "non_jpy_mean_filter_effect": round(other_delta, 5) if other_delta is not None else None,
           "jpy_mean_corr_T1_T2": round(jpy_corr, 4) if jpy_corr is not None else None,
           "non_jpy_mean_corr_T1_T2": round(other_corr, 4) if other_corr is not None else None,
           "label": "DESCRIPTIVE_HYPOTHESIS_GENERATING",
           "note": "N=6 -- this grouping is a descriptive correlate confirmed (again, independently of "
                   "Phase 91) to align with the filter-effect split, NOT a causal claim. 'JPY quote "
                   "currency causes the effect' is explicitly NOT established by anything in this repository."}


# ==========================================================================
# Sec.32 -- required independent verdict classifications
# ==========================================================================
_VALID_INFO_VERDICTS = ("FILTER_INFORMATION_EFFECT_CONFIRMED", "FILTER_INFORMATION_EFFECT_PROMISING",
                        "FILTER_INFORMATION_EFFECT_NOT_CONFIRMED", "FILTER_INFORMATION_EFFECT_INVALIDATED")
_VALID_RISK_VERDICTS = ("RISK_MANAGEMENT_FILTER_CONFIRMED", "RISK_MANAGEMENT_FILTER_PROMISING",
                        "RISK_MANAGEMENT_FILTER_NOT_CONFIRMED")
_VALID_ECON_VERDICTS = ("FILTER_ECONOMIC_EDGE_CONFIRMED", "FILTER_ECONOMIC_EDGE_PROMISING",
                        "FILTER_ECONOMIC_EDGE_NOT_ESTABLISHED", "FILTER_ECONOMIC_EFFECT_NEGATIVE")
_VALID_ATTRIBUTION_VERDICTS = ("PHASE_90_EFFECT_REDUCED_TO_FILTER", "PHASE_90_EFFECT_PARTIALLY_EXPLAINED_BY_FILTER",
                              "PHASE_90_EFFECT_NOT_REPRODUCED", "PHASE_90_EFFECT_INVALIDATED")


def classify_information_effect(rand_placebo: Dict[str, Any], shuf_placebo: Dict[str, Any],
                                exposure_ctrl: Dict[str, Any], threshold_rob: Dict[str, Any],
                                fold_cls: Dict[str, Any]) -> Tuple[str, str]:
    pooled_r, pooled_s = rand_placebo.get("pooled"), shuf_placebo.get("pooled")
    if not pooled_r or not pooled_s:
        return "FILTER_INFORMATION_EFFECT_NOT_CONFIRMED", "Placebo controls could not be computed."
    pctl_r, pctl_s = pooled_r["percentile_of_real"], pooled_s["percentile_of_real"]
    if pctl_r <= 0.10 or pctl_s <= 0.10:
        return "FILTER_INFORMATION_EFFECT_INVALIDATED", \
            f"Real filter underperforms its own equal-retention placebo distribution (percentiles {pctl_r}/{pctl_s})."
    beats_generic = (exposure_ctrl["pooled"]["real_filter"].get("expectancy_R") or 0) > \
                    (exposure_ctrl["pooled"]["generic_exposure_reduction"].get("expectancy_R") or 0)
    n_strong_or_moderate = sum(1 for v in fold_cls.values()
                               if isinstance(v, dict) and v.get("classification") in ("STRONG_CONSISTENCY", "MODERATE_CONSISTENCY"))
    if pctl_r >= 0.95 and pctl_s >= 0.95 and beats_generic and \
       threshold_rob.get("classification") in ("ROBUST", "MODERATELY_SENSITIVE") and n_strong_or_moderate >= 4:
        return "FILTER_INFORMATION_EFFECT_CONFIRMED", \
            (f"Real filter clearly beats both equal-retention placebo controls (percentiles {pctl_r}/{pctl_s}), "
             "beats a deterministic generic exposure-reduction control, survives a modest threshold "
             f"perturbation, and shows consistent fold-level benefit on {n_strong_or_moderate}/6 instruments.")
    if pctl_r >= 0.90 and pctl_s >= 0.90 and beats_generic:
        return "FILTER_INFORMATION_EFFECT_PROMISING", \
            (f"Real filter beats both placebo controls (percentiles {pctl_r}/{pctl_s}) and the generic "
             "exposure-reduction control, but does not yet clear the full robustness/breadth bar for a "
             "confirmed verdict.")
    return "FILTER_INFORMATION_EFFECT_NOT_CONFIRMED", \
        (f"Real filter does not clearly separate from its equal-retention placebo distribution "
         f"(percentiles {pctl_r}/{pctl_s}), or does not beat the generic exposure-reduction control.")


def classify_risk_management_effect(exp_result: Dict[str, Any], dd_attr: Dict[str, Any]) -> Tuple[str, str]:
    dd_deltas = [f["delta_max_drawdown_R"] for f in exp_result["per_fold"] if "delta_max_drawdown_R" in f]
    all_folds_improve = bool(dd_deltas) and all(d > 0 for d in dd_deltas)
    incremental = dd_attr.get("incremental_improvement_beyond_generic_R")
    beats_generic_dd = incremental is not None and incremental > 0
    if all_folds_improve and beats_generic_dd:
        return "RISK_MANAGEMENT_FILTER_CONFIRMED", \
            "Drawdown improves in every walk-forward fold and the improvement exceeds what a generic, " \
            "return-independent exposure reduction of the same size would achieve."
    if dd_deltas and float(np.mean(dd_deltas)) > 0:
        return "RISK_MANAGEMENT_FILTER_PROMISING", \
            "Pooled drawdown improves but not in every fold, or the improvement does not clearly exceed " \
            "the generic exposure-reduction control."
    return "RISK_MANAGEMENT_FILTER_NOT_CONFIRMED", "Drawdown does not clearly improve under the isolated filter."


def classify_economic_effect(exp_result: Dict[str, Any], cost_rob: Dict[str, Any]) -> Tuple[str, str]:
    deltas = [f["delta_expectancy_R"] for f in exp_result["per_fold"] if "delta_expectancy_R" in f]
    if not deltas:
        return "FILTER_ECONOMIC_EDGE_NOT_ESTABLISHED", "Primary experiment could not be computed."
    pooled_delta = float(np.mean(deltas))
    cost_independent = cost_rob.get("classification") == "COST_INDEPENDENT"
    all_folds_positive = all(d > 0 for d in deltas)
    if pooled_delta < -0.001 and all(d < 0 for d in deltas):
        return "FILTER_ECONOMIC_EFFECT_NEGATIVE", f"Pooled expectancy delta ({round(pooled_delta, 5)}) is negative in every fold."
    if all_folds_positive and cost_independent:
        return "FILTER_ECONOMIC_EDGE_CONFIRMED", \
            (f"Pooled expectancy delta ({round(pooled_delta, 5)}) is positive in every fold and across the "
             "full LOWER/BASE/ADVERSE/SEVERE cost grid.")
    if pooled_delta > 0:
        return "FILTER_ECONOMIC_EDGE_PROMISING", \
            (f"Pooled expectancy delta ({round(pooled_delta, 5)}) is positive but not positive in every "
             "fold or across every cost scenario.")
    return "FILTER_ECONOMIC_EDGE_NOT_ESTABLISHED", f"Pooled expectancy delta ({round(pooled_delta, 5)}) is not clearly positive."


def classify_phase90_attribution(info_verdict: str, econ_verdict: str, fold_cls: Dict[str, Any]) -> Tuple[str, str]:
    n_strong_or_moderate = sum(1 for v in fold_cls.values()
                               if isinstance(v, dict) and v.get("classification") in ("STRONG_CONSISTENCY", "MODERATE_CONSISTENCY"))
    if info_verdict == "FILTER_INFORMATION_EFFECT_INVALIDATED":
        return "PHASE_90_EFFECT_INVALIDATED", \
            "The isolated filter fails its own placebo controls -- Phase 90's original combined effect " \
            "cannot be attributed to the eligibility filter under this genuine walk-forward re-test."
    if info_verdict == "FILTER_INFORMATION_EFFECT_CONFIRMED" and \
       econ_verdict in ("FILTER_ECONOMIC_EDGE_CONFIRMED", "FILTER_ECONOMIC_EDGE_PROMISING") and n_strong_or_moderate >= 4:
        return "PHASE_90_EFFECT_REDUCED_TO_FILTER", \
            "Removing sizing entirely and testing the frozen eligibility filter alone under genuine " \
            "walk-forward reproduces Phase 91's decomposition finding: the filter alone, with unit " \
            "exposure, carries essentially the whole of Phase 90's original economic contribution."
    if info_verdict in ("FILTER_INFORMATION_EFFECT_CONFIRMED", "FILTER_INFORMATION_EFFECT_PROMISING") and \
       econ_verdict in ("FILTER_ECONOMIC_EDGE_CONFIRMED", "FILTER_ECONOMIC_EDGE_PROMISING"):
        return "PHASE_90_EFFECT_PARTIALLY_EXPLAINED_BY_FILTER", \
            "The isolated filter shows real, placebo-surviving value without sizing, consistent with " \
            "Phase 91's finding that filtering (not sizing) drives Phase 90's benefit, but breadth/" \
            "robustness is not yet complete enough to say the original effect reduces ENTIRELY to filtering."
    return "PHASE_90_EFFECT_NOT_REPRODUCED", \
        "The isolated filter, tested alone under genuine walk-forward and challenged with placebo/" \
        "robustness controls, does not clearly reproduce Phase 90/91's reported filter benefit."


# ==========================================================================
# result container
# ==========================================================================
@dataclass
class Phase92Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    canonical_horizon: int
    canonical_quantile: float
    cost_scenarios: Dict[str, float]
    random_seeds: Dict[str, int]
    confirmatory_experiment: Dict[str, Any]
    removed_vs_retained: Dict[str, Any]
    randomized_retention_placebo: Dict[str, Any]
    shuffled_filter_placebo: Dict[str, Any]
    exposure_reduction_control: Dict[str, Any]
    directional_contamination: Dict[str, Any]
    direction_neutral_control: Dict[str, Any]
    volatility_confound: Dict[str, Any]
    threshold_robustness: Dict[str, Any]
    magnitude_target_robustness: Dict[str, Any]
    cost_robustness: Dict[str, Any]
    drawdown_attribution: Dict[str, Any]
    fold_level_classification: Dict[str, Any]
    quote_currency_hypothesis: Dict[str, Any]
    filter_information_effect: str
    filter_information_effect_reason: str
    risk_management_filter_effect: str
    risk_management_filter_reason: str
    filter_economic_effect: str
    filter_economic_effect_reason: str
    phase90_attribution: str
    phase90_attribution_reason: str
    determinism: Dict[str, Any]
    directional_edge_found: bool = False
    magnitude_signal_found: bool = True
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


def run() -> Phase92Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()

    conf_1 = run_confirmatory_experiment(COST_SCENARIOS["BASE"])
    conf_2 = run_confirmatory_experiment(COST_SCENARIOS["BASE"])
    determinism_match = (conf_1 == conf_2)
    confirmatory = conf_1

    removed_retained = removed_vs_retained_analysis()
    rand_placebo = randomized_retention_placebo()
    shuf_placebo = shuffled_filter_placebo()
    exposure_ctrl = exposure_reduction_control()
    directional = directional_contamination_test()
    direction_neutral = direction_neutral_control()
    vol_confound = volatility_confound_test()
    threshold_rob = threshold_robustness()
    target_rob = magnitude_target_robustness()
    cost_rob = cost_robustness()
    dd_attr = drawdown_attribution()
    fold_cls = fold_level_classification(confirmatory)
    quote_hyp = quote_currency_hypothesis_test(confirmatory, directional)

    info_verdict, info_reason = classify_information_effect(rand_placebo, shuf_placebo, exposure_ctrl, threshold_rob, fold_cls)
    risk_verdict, risk_reason = classify_risk_management_effect(confirmatory, dd_attr)
    econ_verdict, econ_reason = classify_economic_effect(confirmatory, cost_rob)
    attribution_verdict, attribution_reason = classify_phase90_attribution(info_verdict, econ_verdict, fold_cls)

    ident = json.dumps({"schema": SCHEMA_VERSION, "info_verdict": info_verdict, "econ_verdict": econ_verdict,
                       "risk_verdict": risk_verdict, "attribution_verdict": attribution_verdict,
                       "confirmatory_base": confirmatory}, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase92Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(INSTRUMENTS_83), timeframe=PRIMARY_TF, canonical_horizon=_HORIZON,
        canonical_quantile=_ELIGIBILITY_QUANTILE, cost_scenarios={"LOWER": _LOWER_COST, **COST_SCENARIOS},
        random_seeds={"randomized_retention_placebo": _RAND_PLACEBO_SEED, "shuffled_filter_placebo": _SHUF_PLACEBO_SEED},
        confirmatory_experiment=confirmatory, removed_vs_retained=removed_retained,
        randomized_retention_placebo=rand_placebo, shuffled_filter_placebo=shuf_placebo,
        exposure_reduction_control=exposure_ctrl, directional_contamination=directional,
        direction_neutral_control=direction_neutral, volatility_confound=vol_confound,
        threshold_robustness=threshold_rob, magnitude_target_robustness=target_rob, cost_robustness=cost_rob,
        drawdown_attribution=dd_attr, fold_level_classification=fold_cls, quote_currency_hypothesis=quote_hyp,
        filter_information_effect=info_verdict, filter_information_effect_reason=info_reason,
        risk_management_filter_effect=risk_verdict, risk_management_filter_reason=risk_reason,
        filter_economic_effect=econ_verdict, filter_economic_effect_reason=econ_reason,
        phase90_attribution=attribution_verdict, phase90_attribution_reason=attribution_reason,
        determinism={"match": determinism_match}, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase92Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase92_standalone_filter_validation", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 92 - standalone magnitude eligibility filter validation ...", flush=True)
    res = run()
    print(f"\n=== PHASE 92 ({res.runtime_seconds}s) ===")
    print(f"\nConfirmatory (per-fold pooled): "
         f"{json.dumps([{k: v for k, v in f.items() if k != 'per_instrument'} for f in res.confirmatory_experiment['per_fold']], default=str)}")
    print(f"\nRandomized-retention placebo (pooled): {json.dumps(res.randomized_retention_placebo.get('pooled'), default=str)}")
    print(f"\nShuffled-filter placebo (pooled): {json.dumps(res.shuffled_filter_placebo.get('pooled'), default=str)}")
    print(f"\nExposure-reduction control (pooled): {json.dumps(res.exposure_reduction_control.get('pooled'), default=str)}")
    print(f"\nVolatility confound (pooled): {json.dumps(res.volatility_confound.get('pooled'), default=str)}")
    print(f"\nThreshold robustness: {json.dumps(res.threshold_robustness, default=str)}")
    print(f"\nMagnitude target robustness: {json.dumps(res.magnitude_target_robustness, default=str)}")
    print(f"\nCost robustness: {json.dumps(res.cost_robustness, default=str)}")
    print(f"\nDrawdown attribution: {json.dumps(res.drawdown_attribution, default=str)}")
    print(f"\nFold-level classification: {json.dumps(res.fold_level_classification, default=str)}")
    print(f"\nQuote-currency hypothesis: {json.dumps(res.quote_currency_hypothesis, default=str)}")
    print(f"\nDeterminism: {res.determinism}")
    print(f"\nFILTER_INFORMATION_EFFECT: {res.filter_information_effect} -- {res.filter_information_effect_reason}")
    print(f"RISK_MANAGEMENT_FILTER_EFFECT: {res.risk_management_filter_effect} -- {res.risk_management_filter_reason}")
    print(f"FILTER_ECONOMIC_EFFECT: {res.filter_economic_effect} -- {res.filter_economic_effect_reason}")
    print(f"PHASE_90_ATTRIBUTION: {res.phase90_attribution} -- {res.phase90_attribution_reason}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DESIGN_NOTE", "run_confirmatory_experiment",
    "removed_vs_retained_analysis", "randomized_retention_placebo", "shuffled_filter_placebo",
    "exposure_reduction_control", "directional_contamination_test", "direction_neutral_control",
    "volatility_confound_test", "threshold_robustness", "magnitude_target_robustness", "cost_robustness",
    "drawdown_attribution", "fold_level_classification", "quote_currency_hypothesis_test",
    "classify_information_effect", "classify_risk_management_effect", "classify_economic_effect",
    "classify_phase90_attribution", "run", "persist", "get_result", "main",
]
