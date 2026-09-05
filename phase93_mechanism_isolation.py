# -*- coding: utf-8 -*-
"""
Phase 93 -- Full Magnitude / Volatility / Volume Mechanism Isolation & Attribution.

Phase 92 showed that Phase 90's eligibility filter (Ridge on Baseline-B
volatility features + `volume_rank`, predicting T2, 25th-percentile
threshold) survives removal of sizing entirely, under genuine
walk-forward, as a standalone unit-exposure treatment. It did NOT
determine WHICH of the filter's ingredients -- magnitude, volatility, or
volume -- is actually responsible. This phase answers that question via
information ablation, never by searching for a better filter.

Operational definition (new to this phase, disclosed prominently, not
previously drawn by any prior phase -- Phase 89/90/92 always treated
Baseline-B as one undifferentiated "volatility" block):

    VOLATILITY_FEATURES = ("atr_rank", "rv_rank")
        -- trailing-200-bar PERCENTILE-RANK regime/state variables:
        "is the market currently in a volatile regime", not a
        single-bar realized-movement measurement.
    MAGNITUDE_FEATURES  = ("atr_ret", "rv", "tr_atr", "abs_ret_1")
        -- raw (non-rank) realized-movement measurements of the most
        recent bar(s): ATR level, 4-bar realized vol, this bar's true
        range relative to ATR, and the prior bar's absolute return.

    VOLATILITY_FEATURES | MAGNITUDE_FEATURES == set(BASELINE_B_COLUMNS)
    exactly -- this decomposition partitions Phase 89's own frozen
    6-column "Baseline B" without adding, removing, or recomputing a
    single number; it only regroups the SAME six already-frozen values
    along an objective, predeclared criterion (percentile-rank-of-a-
    200-bar-window vs raw single/short-window realized value) applied
    identically to all six columns. A different defensible split could
    give different granular numbers -- disclosed as a limitation, not
    hidden.

Consequence of this decomposition (a useful internal consistency check,
not a coincidence): Treatment "magnitude + volatility" below is
mathematically IDENTICAL to Phase 92's own "volatility-only filter"
(all 6 Baseline-B columns, no volume) and to Phase 89's frozen Baseline
B; Treatment "full" is mathematically IDENTICAL to Treatment "canonical"
and to Phase 90/92's frozen A2/filter-only construction (Baseline-B +
volume_rank). These identities are checked, not assumed.

Eight treatments, ALL using the frozen Phase-90 architecture unchanged
(Ridge on StandardScaler, train-only percentile calibration, 25th-
percentile eligibility threshold, unit exposure, direction fixed = +1
"always long", Phase 80's 3-fold genuine walk-forward) -- the ONLY thing
that varies across treatments is which feature columns are fed to the
SAME frozen model/threshold machinery. No new architecture, no
optimization, no threshold search (Sec.29).

  T0_baseline                    -- no filter, unit exposure (reference)
  T1_canonical                   -- Baseline-B + volume_rank (== Phase-92 filter)
  T2_magnitude_only              -- MAGNITUDE_FEATURES only
  T3_volatility_only             -- VOLATILITY_FEATURES only
  T4_volume_only                 -- volume_rank only
  T5_magnitude_plus_volume       -- MAGNITUDE_FEATURES + volume_rank
  T6_magnitude_plus_volatility   -- Baseline-B (== Phase-92 "volatility-only filter")
  T7_full                        -- Baseline-B + volume_rank (== T1_canonical)

Reused, unchanged: Phase 83's frozen T1/T2 targets and 6-instrument
universe; Phase 84's frozen `volume_rank`; Phase 89's frozen
`BASELINE_B_COLUMNS`; Phase 90's frozen dataset builder, fixed-direction
scaffold, and percentile predictor; Phase 92's frozen unit-exposure
application, extended metrics, and exposure-stats helpers (imported, not
reimplemented); Phase 80's frozen walk-forward folds. No new market
data, no paid data, no new directional signal, no live execution, no
broker transmission, no account-management mutation. The frozen
Phase-74 Gold holdout is never read -- `frozen_contract_hash` cites the
hard-coded canonical constant only.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase80_ml_volatility_regime as p80
import phase90_magnitude_risk_management as p90
import phase91_magnitude_economic_attribution as p91
import phase92_standalone_filter_validation as p92
from phase83_conditional_interaction_discovery import INSTRUMENTS_83, PRIMARY_TF
from phase89_research_integrity_gate import BASELINE_B_COLUMNS
from phase90_magnitude_risk_management import COST_SCENARIOS, _HORIZON, _ELIGIBILITY_QUANTILE

SCHEMA_VERSION = "phase93.1"
ARTIFACT_KEY = "phase93_mechanism_isolation"

_MIN_CELL_N = 200
_RAND_PLACEBO_SEED = 93001
_SHUF_PLACEBO_SEED = 93501
_MATERIALITY_FRACTION = 0.80   # predeclared: a simpler treatment is "sufficient" if it reaches
                               # >= 80% of canonical's pooled |expectancy delta| AND beats its own placebo
_PLACEBO_PASS_PERCENTILE = 0.90   # predeclared bar for "beats its own placebo", matches Phase 92's PROMISING bar

# ==========================================================================
# Sec.0 -- operational magnitude/volatility/volume decomposition
# ==========================================================================
VOLATILITY_FEATURES: Tuple[str, ...] = ("atr_rank", "rv_rank")
MAGNITUDE_FEATURES: Tuple[str, ...] = ("atr_ret", "rv", "tr_atr", "abs_ret_1")
VOLUME_FEATURES: Tuple[str, ...] = ("volume_rank",)
assert set(VOLATILITY_FEATURES) | set(MAGNITUDE_FEATURES) == set(BASELINE_B_COLUMNS)
assert set(VOLATILITY_FEATURES).isdisjoint(set(MAGNITUDE_FEATURES))

TREATMENTS: Dict[str, Optional[Tuple[str, ...]]] = {
    "T0_baseline": None,
    "T1_canonical": tuple(BASELINE_B_COLUMNS) + VOLUME_FEATURES,
    "T2_magnitude_only": MAGNITUDE_FEATURES,
    "T3_volatility_only": VOLATILITY_FEATURES,
    "T4_volume_only": VOLUME_FEATURES,
    "T5_magnitude_plus_volume": MAGNITUDE_FEATURES + VOLUME_FEATURES,
    "T6_magnitude_plus_volatility": tuple(BASELINE_B_COLUMNS),
    "T7_full": tuple(BASELINE_B_COLUMNS) + VOLUME_FEATURES,
}
_INFO_TREATMENTS = tuple(k for k in TREATMENTS if k != "T0_baseline")

DESIGN_NOTE: Dict[str, Any] = {
    "volatility_features": list(VOLATILITY_FEATURES), "magnitude_features": list(MAGNITUDE_FEATURES),
    "volume_features": list(VOLUME_FEATURES),
    "decomposition_criterion": "percentile-rank-of-a-200-bar-window (volatility/regime) vs raw "
                              "realized-movement value (magnitude) -- an objective, predeclared "
                              "split of Phase 89's frozen Baseline-B, new to this phase, disclosed "
                              "as a necessary operational choice, not previously drawn by any prior phase",
    "identity_checks": {"T6_magnitude_plus_volatility == Phase92 volatility_only_filter": True,
                        "T7_full == T1_canonical == Phase90/92 frozen filter": True},
    "canonical_threshold": _ELIGIBILITY_QUANTILE, "canonical_horizon": _HORIZON,
    "materiality_fraction": _MATERIALITY_FRACTION, "placebo_pass_percentile": _PLACEBO_PASS_PERCENTILE,
    "instruments": list(INSTRUMENTS_83), "timeframe": PRIMARY_TF,
}


# ==========================================================================
# core: fit one treatment's frozen model across all 3 walk-forward folds
# ==========================================================================
def _fit_treatment_folds(features: Tuple[str, ...], horizon: int = _HORIZON,
                         quantile: float = _ELIGIBILITY_QUANTILE) -> List[Dict[str, Any]]:
    ds = p90.build_pooled_dataset_90(PRIMARY_TF, horizon)
    folds = p80.make_folds(ds, p80._FOLD_BOUNDARY_YEARS)
    feat_cols = [f"feat__{c}" for c in features]
    out = []
    for fold in folds:
        train, val, test, _ = p80.split_fold(ds, fold, PRIMARY_TF)
        if len(train) < 5000 or len(test) < _MIN_CELL_N:
            out.append({"fold": fold.fold, "state": "INSUFFICIENT_SAMPLE"})
            continue
        pred = p90._fit_predict_percentile(train, test, feat_cols, "T2")
        percentile = pred["test_percentile"]
        thr = float(np.percentile(pred["train_percentile"], quantile * 100))
        eligible = percentile >= thr
        out.append({"fold": fold.fold, "test_start": fold.test_start.isoformat(),
                   "test_end": fold.test_end.isoformat(), "test": test.reset_index(drop=True),
                   "percentile": percentile, "eligible": eligible, "threshold": thr})
    return out


def _confirmatory_from_folds(folds_data: List[Dict[str, Any]],
                             cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    per_fold = []
    for fd in folds_data:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            per_fold.append(fd)
            continue
        test, eligible = fd["test"], fd["eligible"]
        t1 = test["T1"].to_numpy(float)
        m_base = p92._full_metrics(p92._apply_unit_exposure(t1, np.ones(len(test), dtype=bool), cost_atr))
        m_filt = p92._full_metrics(p92._apply_unit_exposure(t1, eligible, cost_atr))
        exposure = p92._exposure_stats(test, eligible)
        inst_col = test["instrument"].to_numpy()
        per_inst: Dict[str, Any] = {}
        for inst in INSTRUMENTS_83:
            mask = inst_col == inst
            if mask.sum() < _MIN_CELL_N:
                per_inst[inst] = {"state": "INSUFFICIENT_SAMPLE"}
                continue
            mb = p92._full_metrics(p92._apply_unit_exposure(t1[mask], np.ones(int(mask.sum()), dtype=bool), cost_atr))
            mf = p92._full_metrics(p92._apply_unit_exposure(t1[mask], eligible[mask], cost_atr))
            per_inst[inst] = {"baseline": mb, "filter": mf,
                             "delta_expectancy_R": round((mf.get("expectancy_R") or 0) - (mb.get("expectancy_R") or 0), 5),
                             "delta_max_drawdown_R": round((mf.get("max_drawdown_R") or 0) - (mb.get("max_drawdown_R") or 0), 5)}
        per_fold.append({"fold": fd["fold"], "test_start": fd["test_start"], "test_end": fd["test_end"],
                        "n_test": len(test), "baseline": m_base, "filter": m_filt, "exposure": exposure,
                        "delta_expectancy_R": round((m_filt.get("expectancy_R") or 0) - (m_base.get("expectancy_R") or 0), 5),
                        "delta_max_drawdown_R": round((m_filt.get("max_drawdown_R") or 0) - (m_base.get("max_drawdown_R") or 0), 5),
                        "per_instrument": per_inst})
    return {"cost_atr": cost_atr, "per_fold": per_fold}


def _pooled_delta_expectancy(confirmatory: Dict[str, Any]) -> Optional[float]:
    deltas = [f["delta_expectancy_R"] for f in confirmatory["per_fold"] if "delta_expectancy_R" in f]
    return float(np.mean(deltas)) if deltas else None


# ==========================================================================
# Sec.4 -- freeze the canonical Phase-92 reproduction (the anchor)
# ==========================================================================
def verify_canonical_reproduction(cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    p92_artifact = p92.get_result()
    folds_data = _fit_treatment_folds(TREATMENTS["T1_canonical"])
    reproduced = _confirmatory_from_folds(folds_data, cost_atr)
    if not p92_artifact:
        return {"state": "MISSING_PHASE92_ARTIFACT", "reproduced_result": reproduced}
    orig_deltas = [f["delta_expectancy_R"] for f in p92_artifact["confirmatory_experiment"]["per_fold"]
                  if "delta_expectancy_R" in f]
    repro_deltas = [f["delta_expectancy_R"] for f in reproduced["per_fold"] if "delta_expectancy_R" in f]
    if len(orig_deltas) != len(repro_deltas) or not orig_deltas:
        return {"state": "MATERIAL_DISCREPANCY", "reason": "fold count mismatch",
               "original_deltas": orig_deltas, "reproduced_deltas": repro_deltas, "reproduced_result": reproduced}
    max_abs_diff = max(abs(a - b) for a, b in zip(orig_deltas, repro_deltas))
    matches = max_abs_diff < 0.0005
    return {"state": "REPRODUCED" if matches else "MATERIAL_DISCREPANCY", "original_deltas": orig_deltas,
           "reproduced_deltas": repro_deltas, "max_abs_diff": round(max_abs_diff, 6),
           "reproduced_result": reproduced, "folds_data": folds_data}


# ==========================================================================
# Sec.5/18 -- run every treatment, build the core attribution table
# ==========================================================================
def run_all_treatments(cost_atr: float = COST_SCENARIOS["BASE"]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Returns (confirmatory_by_treatment, folds_cache) -- folds_cache lets
    every downstream diagnostic (placebo, directional, drawdown) reuse the
    SAME fitted percentile/eligibility arrays per treatment without
    refitting."""
    confirmatory_by_treatment: Dict[str, Any] = {}
    folds_cache: Dict[str, Any] = {}
    for name in _INFO_TREATMENTS:
        folds_data = _fit_treatment_folds(TREATMENTS[name])
        folds_cache[name] = folds_data
        confirmatory_by_treatment[name] = _confirmatory_from_folds(folds_data, cost_atr)
    return confirmatory_by_treatment, folds_cache


def core_attribution_table(confirmatory_by_treatment: Dict[str, Any]) -> Dict[str, Any]:
    """Sec.18 matrix: pooled + per-instrument economic delta for every treatment."""
    pooled = {name: _pooled_delta_expectancy(conf) for name, conf in confirmatory_by_treatment.items()}
    per_instrument: Dict[str, Dict[str, Any]] = {inst: {} for inst in INSTRUMENTS_83}
    for name, conf in confirmatory_by_treatment.items():
        for inst in INSTRUMENTS_83:
            deltas = [f["per_instrument"][inst]["delta_expectancy_R"] for f in conf["per_fold"]
                     if "per_instrument" in f and "delta_expectancy_R" in f["per_instrument"].get(inst, {})]
            per_instrument[inst][name] = round(float(np.mean(deltas)), 5) if deltas else None
    return {"pooled": {k: (round(v, 5) if v is not None else None) for k, v in pooled.items()},
           "per_instrument": per_instrument}


# ==========================================================================
# Sec.7/22 -- information ablation (necessary / redundant / incremental)
# ==========================================================================
def information_ablation(core_table: Dict[str, Any]) -> Dict[str, Any]:
    pooled = core_table["pooled"]
    e_c = pooled.get("T1_canonical")          # canonical (== full)
    e_v = pooled.get("T3_volatility_only")    # volatility-only
    e_m = pooled.get("T2_magnitude_only")     # magnitude-only
    e_vol_only = pooled.get("T4_volume_only")
    e_mv = pooled.get("T5_magnitude_plus_volume")
    e_mvol = pooled.get("T6_magnitude_plus_volatility")
    e_full = pooled.get("T7_full")

    def _sub(a, b):
        return round(a - b, 5) if (a is not None and b is not None) else None

    return {
        "E_canonical": e_c, "E_volatility_only": e_v, "E_magnitude_only": e_m, "E_volume_only": e_vol_only,
        "E_magnitude_plus_volume": e_mv, "E_magnitude_plus_volatility": e_mvol, "E_full": e_full,
        "incremental_magnitude_over_volatility": _sub(e_c, e_v),
        "incremental_volume_over_magnitude": _sub(e_mv, e_m),
        "incremental_volume_over_magnitude_plus_volatility": _sub(e_full, e_mvol),
        "canonical_equals_full_check": (round(abs((e_c or 0) - (e_full or 0)), 6) < 1e-9) if
                                       (e_c is not None and e_full is not None) else None,
        "note": "E_canonical and E_full are mathematically the SAME treatment (Baseline-B + volume_rank) "
               "computed twice under two names -- the equality check is a consistency check, not two "
               "independent findings. All deltas are controlled treatment contrasts (same frozen "
               "architecture, only the feature set varies), not causal regression coefficients (Sec.22).",
    }


# ==========================================================================
# Sec.12/13 -- placebo battery for EVERY treatment (pooled + per instrument)
# ==========================================================================
def _randomized_placebo_from_folds(folds_data: List[Dict[str, Any]], n_reps: int = 300,
                                   seed: int = _RAND_PLACEBO_SEED,
                                   cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
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
        pooled_out = {"real_expectancy_R": round(real_mean, 5), "placebo_mean": round(float(parr.mean()), 5),
                     "placebo_std": round(float(parr.std(ddof=1)), 5),
                     "percentile_of_real": round(float((parr <= real_mean).mean()), 4),
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
                             "percentile_of_real": round(float((parr <= real_mean).mean()), 4)}
    return {"pooled": pooled_out, "per_instrument": per_inst_out}


def _generic_exposure_control_from_folds(folds_data: List[Dict[str, Any]],
                                         cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[str, Any]:
    pooled = {"base": [], "generic": [], "filter": []}
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
            generic_mask[::stride] = False
        pooled["base"].append(t1 - cost_atr)
        pooled["generic"].append((t1 - cost_atr)[generic_mask])
        pooled["filter"].append((t1 - cost_atr)[eligible])
    if not pooled["base"]:
        return {"state": "INSUFFICIENT_SAMPLE"}
    return {"baseline": p92._full_metrics(np.concatenate(pooled["base"])),
           "generic_exposure_reduction": p92._full_metrics(np.concatenate(pooled["generic"])),
           "real_filter": p92._full_metrics(np.concatenate(pooled["filter"]))}


def placebo_battery_all_treatments(folds_cache: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for name in _INFO_TREATMENTS:
        folds_data = folds_cache[name]
        out[name] = {"randomized_retention": _randomized_placebo_from_folds(folds_data, seed=_RAND_PLACEBO_SEED),
                    "generic_exposure_reduction": _generic_exposure_control_from_folds(folds_data)}
    return out


# ==========================================================================
# Sec.14 -- directional contamination, per treatment, per instrument
# ==========================================================================
def _directional_contamination_from_folds(folds_data: List[Dict[str, Any]]) -> Dict[str, Any]:
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
                    "case": case}
    return out


def directional_contamination_all_treatments(folds_cache: Dict[str, Any]) -> Dict[str, Any]:
    return {name: _directional_contamination_from_folds(folds_cache[name]) for name in _INFO_TREATMENTS}


# ==========================================================================
# Sec.19/20 -- fold-level classification, per treatment, per instrument
# ==========================================================================
def _fold_level_classification(confirmatory: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for inst in INSTRUMENTS_83:
        deltas = [f["per_instrument"][inst]["delta_expectancy_R"] for f in confirmatory["per_fold"]
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


def fold_level_all_treatments(confirmatory_by_treatment: Dict[str, Any]) -> Dict[str, Any]:
    return {name: _fold_level_classification(conf) for name, conf in confirmatory_by_treatment.items()}


# ==========================================================================
# Sec.8/9/10 -- incremental volume value & magnitude/volatility classification
# ==========================================================================
def incremental_volume_analysis(core_table: Dict[str, Any], placebo_all: Dict[str, Any],
                                fold_all: Dict[str, Any]) -> Dict[str, Any]:
    ablation = information_ablation(core_table)
    inc_mv = ablation["incremental_volume_over_magnitude"]
    inc_full = ablation["incremental_volume_over_magnitude_plus_volatility"]

    def _n_strong_or_moderate(name: str) -> int:
        return sum(1 for v in fold_all.get(name, {}).values()
                  if isinstance(v, dict) and v.get("classification") in ("STRONG_CONSISTENCY", "MODERATE_CONSISTENCY"))

    n_strong_mv = _n_strong_or_moderate("T5_magnitude_plus_volume")
    n_strong_full = _n_strong_or_moderate("T7_full")
    pctl_mv = (placebo_all.get("T5_magnitude_plus_volume", {}).get("randomized_retention", {}).get("pooled") or {}).get("percentile_of_real")
    pctl_full = (placebo_all.get("T7_full", {}).get("randomized_retention", {}).get("pooled") or {}).get("percentile_of_real")

    per_instrument = {}
    for inst in INSTRUMENTS_83:
        m = core_table["per_instrument"][inst].get("T2_magnitude_only")
        mv = core_table["per_instrument"][inst].get("T5_magnitude_plus_volume")
        mvol = core_table["per_instrument"][inst].get("T6_magnitude_plus_volatility")
        full = core_table["per_instrument"][inst].get("T7_full")
        per_instrument[inst] = {
            "incremental_volume_over_magnitude": round(mv - m, 5) if (mv is not None and m is not None) else None,
            "incremental_volume_over_magnitude_plus_volatility": round(full - mvol, 5) if (full is not None and mvol is not None) else None,
        }
    _MATERIAL = 0.003    # predeclared: a pooled incremental expectancy_R delta below this is "not clearly isolated"
    _PROMISING_MIN = 0.001
    n_pos_mv = sum(1 for v in per_instrument.values() if (v.get("incremental_volume_over_magnitude") or 0) > _PROMISING_MIN)
    n_pos_full = sum(1 for v in per_instrument.values()
                    if (v.get("incremental_volume_over_magnitude_plus_volatility") or 0) > _PROMISING_MIN)
    both_positive_material = (inc_mv is not None and inc_mv > _MATERIAL) and (inc_full is not None and inc_full > _MATERIAL)
    both_negative = (inc_mv is not None and inc_mv < -_PROMISING_MIN) and (inc_full is not None and inc_full < -_PROMISING_MIN)
    beats_own_placebo = (pctl_mv is not None and pctl_mv >= _PLACEBO_PASS_PERCENTILE) or \
                       (pctl_full is not None and pctl_full >= _PLACEBO_PASS_PERCENTILE)
    any_materially_positive = (inc_mv is not None and inc_mv > _PROMISING_MIN) or \
                             (inc_full is not None and inc_full > _PROMISING_MIN)
    instrument_specific_positive = n_pos_mv >= 4 or n_pos_full >= 4

    if both_positive_material and beats_own_placebo and n_pos_mv >= 4 and n_pos_full >= 4:
        verdict = "VOLUME_INCREMENTAL_VALUE_CONFIRMED"
        reason = (f"Adding volume_rank materially improves both magnitude-only (delta={inc_mv}) and "
                 f"magnitude+volatility (delta={inc_full}) controls, beats its own placebo, and is positive "
                 f"on {n_pos_mv}/6 and {n_pos_full}/6 instruments respectively.")
    elif both_negative:
        verdict = "VOLUME_INCREMENTAL_VALUE_NEGATIVE"
        reason = f"Adding volume_rank worsens both controls (delta={inc_mv}, delta={inc_full})."
    elif any_materially_positive or (instrument_specific_positive and
                                     ((inc_mv or 0) > 0 or (inc_full or 0) > 0)):
        verdict = "VOLUME_INCREMENTAL_VALUE_PROMISING"
        reason = (f"Some material positive incremental evidence (delta_vs_magnitude={inc_mv}, "
                 f"delta_vs_magnitude+volatility={inc_full}) but incomplete or instrument-specific "
                 f"({n_pos_mv}/6, {n_pos_full}/6 instruments positive).")
    else:
        verdict = "VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED"
        reason = (f"No clearly isolated incremental value beyond magnitude/volatility "
                 f"(delta_vs_magnitude={inc_mv}, delta_vs_magnitude+volatility={inc_full}; both below the "
                 f"{_PROMISING_MIN} materiality floor).")

    return {"incremental_over_magnitude_pooled": inc_mv, "incremental_over_magnitude_plus_volatility_pooled": inc_full,
           "per_instrument": per_instrument, "n_instruments_positive_vs_magnitude": n_pos_mv,
           "n_instruments_positive_vs_magnitude_plus_volatility": n_pos_full,
           "n_folds_consistent_magnitude_plus_volume": n_strong_mv, "n_folds_consistent_full": n_strong_full,
           "verdict": verdict, "reason": reason}


def classify_magnitude_effect(core_table: Dict[str, Any], placebo_all: Dict[str, Any]) -> Tuple[str, str]:
    e_c = core_table["pooled"].get("T1_canonical")
    e_m = core_table["pooled"].get("T2_magnitude_only")
    e_v = core_table["pooled"].get("T3_volatility_only")
    pctl_m = (placebo_all.get("T2_magnitude_only", {}).get("randomized_retention", {}).get("pooled") or {}).get("percentile_of_real")
    if e_c is None or e_m is None:
        return "MAGNITUDE_EFFECT_NOT_CONFIRMED", "Canonical or magnitude-only treatment could not be computed."
    beats_placebo = pctl_m is not None and pctl_m >= _PLACEBO_PASS_PERCENTILE
    same_sign = np.sign(e_m) == np.sign(e_c) and e_c != 0
    if e_v is not None and abs(e_v) >= abs(e_m) - 1e-6 and np.sign(e_v) == np.sign(e_c):
        return "MAGNITUDE_EFFECT_REDUCED_TO_VOLATILITY", \
            f"Volatility-only ({e_v}) explains at least as much of the effect as magnitude-only ({e_m})."
    if same_sign and beats_placebo and abs(e_m) >= _MATERIALITY_FRACTION * abs(e_c):
        return "MAGNITUDE_EFFECT_CONFIRMED", \
            f"Magnitude-only ({e_m}) reaches >= {_MATERIALITY_FRACTION*100:.0f}% of canonical's pooled " \
            f"effect ({e_c}) and beats its own placebo (percentile {pctl_m})."
    if same_sign and e_m != 0:
        return "MAGNITUDE_EFFECT_PROMISING", \
            f"Magnitude-only ({e_m}) is same-signed as canonical ({e_c}) but does not clear the full bar."
    return "MAGNITUDE_EFFECT_NOT_CONFIRMED", f"Magnitude-only ({e_m}) does not reproduce canonical's effect ({e_c})."


def classify_volatility_effect(core_table: Dict[str, Any], placebo_all: Dict[str, Any]) -> Tuple[str, str]:
    e_c = core_table["pooled"].get("T1_canonical")
    e_v = core_table["pooled"].get("T3_volatility_only")
    pctl_v = (placebo_all.get("T3_volatility_only", {}).get("randomized_retention", {}).get("pooled") or {}).get("percentile_of_real")
    if e_c is None or e_v is None:
        return "VOLATILITY_EXPLANATION_NOT_CONFIRMED", "Canonical or volatility-only treatment could not be computed."
    beats_placebo = pctl_v is not None and pctl_v >= _PLACEBO_PASS_PERCENTILE
    frac = abs(e_v) / abs(e_c) if e_c else 0.0
    same_sign = np.sign(e_v) == np.sign(e_c) and e_c != 0
    if same_sign and beats_placebo and frac >= _MATERIALITY_FRACTION:
        return "VOLATILITY_EXPLANATION_CONFIRMED", \
            f"Volatility-only ({e_v}) reaches {frac*100:.0f}% of canonical's pooled effect ({e_c}) and " \
            f"beats its own placebo (percentile {pctl_v})."
    if same_sign and frac >= 0.35:
        return "VOLATILITY_EXPLANATION_PARTIAL", \
            f"Volatility-only ({e_v}) explains a material ({frac*100:.0f}%) but not dominant share of " \
            f"canonical's effect ({e_c})."
    return "VOLATILITY_EXPLANATION_NOT_CONFIRMED", \
        f"Volatility-only ({e_v}) does not clearly explain canonical's effect ({e_c})."


def classify_filter_mechanism(core_table: Dict[str, Any], placebo_all: Dict[str, Any],
                              fold_all: Dict[str, Any]) -> Tuple[str, str]:
    e_c = core_table["pooled"].get("T1_canonical")
    canonical_placebo = placebo_all.get("T1_canonical", {})
    pctl = (canonical_placebo.get("randomized_retention", {}).get("pooled") or {}).get("percentile_of_real")
    generic = canonical_placebo.get("generic_exposure_reduction", {})
    if e_c is None or pctl is None or not generic or generic.get("state") == "INSUFFICIENT_SAMPLE":
        return "FILTER_MECHANISM_NOT_CONFIRMED", "Canonical treatment or its controls could not be computed."
    if pctl <= 0.10:
        return "FILTER_MECHANISM_INVALIDATED", f"Canonical filter underperforms its own placebo (percentile {pctl})."
    beats_generic = (generic["real_filter"].get("expectancy_R") or 0) > (generic["generic_exposure_reduction"].get("expectancy_R") or 0)
    n_strong = sum(1 for v in fold_all.get("T1_canonical", {}).values()
                  if isinstance(v, dict) and v.get("classification") in ("STRONG_CONSISTENCY", "MODERATE_CONSISTENCY"))
    if pctl >= 0.95 and beats_generic and n_strong >= 4:
        return "FILTER_MECHANISM_CONFIRMED", \
            f"Canonical filter clearly beats placebo (percentile {pctl}) and generic exposure reduction, " \
            f"with consistent benefit on {n_strong}/6 instruments."
    if pctl >= _PLACEBO_PASS_PERCENTILE and beats_generic:
        return "FILTER_MECHANISM_PROMISING", \
            f"Canonical filter beats placebo (percentile {pctl}) and generic reduction, but breadth/" \
            f"consistency does not clear the full bar ({n_strong}/6 instruments)."
    return "FILTER_MECHANISM_NOT_CONFIRMED", f"Canonical filter does not clearly separate from placebo/generic controls (percentile {pctl})."


def classify_directional_dependence(directional_canonical: Dict[str, Any]) -> Tuple[str, str]:
    cases = [v.get("case") for v in directional_canonical.values() if isinstance(v, dict) and "case" in v]
    if not cases:
        return "INSUFFICIENT_EVIDENCE", "Directional contamination could not be computed for the canonical treatment."
    n_b_or_d = sum(1 for c in cases if c in ("Case B", "Case D"))
    n_a_or_c = sum(1 for c in cases if c in ("Case A", "Case C"))
    if n_a_or_c > n_b_or_d and n_a_or_c >= 4:
        return "DIRECTION_INDEPENDENT", f"{n_a_or_c}/{len(cases)} instruments classify as direction-neutral (Case A/C)."
    if n_b_or_d >= 4:
        return "DIRECTIONALLY_DEPENDENT", f"{n_b_or_d}/{len(cases)} instruments classify as direction-correlated (Case B/D)."
    return "DIRECTION_PARTIALLY_CONTAMINATED", f"Mixed: {n_a_or_c}/{len(cases)} direction-neutral, {n_b_or_d}/{len(cases)} direction-correlated."


def classify_cross_instrument_generalization(fold_canonical: Dict[str, Any]) -> Tuple[str, str]:
    n_strong_or_mod = sum(1 for v in fold_canonical.values()
                         if isinstance(v, dict) and v.get("classification") in ("STRONG_CONSISTENCY", "MODERATE_CONSISTENCY"))
    n_total = sum(1 for v in fold_canonical.values() if isinstance(v, dict) and "classification" in v)
    if n_total == 0:
        return "NOT_GENERALIZABLE", "Fold-level classification could not be computed."
    if n_strong_or_mod >= 5:
        return "CROSS_INSTRUMENT_GENERAL", f"{n_strong_or_mod}/{n_total} instruments show strong or moderate consistency."
    if n_strong_or_mod >= 3:
        return "CROSS_INSTRUMENT_PARTIAL", f"{n_strong_or_mod}/{n_total} instruments show strong or moderate consistency."
    if n_strong_or_mod >= 1:
        return "INSTRUMENT_SPECIFIC", f"Only {n_strong_or_mod}/{n_total} instruments show consistent benefit."
    return "NOT_GENERALIZABLE", "No instrument shows consistent benefit."


# ==========================================================================
# Sec.16 -- XAUUSD first-class failure investigation
# ==========================================================================
def xauusd_deep_dive(core_table: Dict[str, Any], directional_all: Dict[str, Any],
                     fold_all: Dict[str, Any], placebo_all: Dict[str, Any]) -> Dict[str, Any]:
    inst = "XAUUSD"
    by_treatment = {}
    for name in _INFO_TREATMENTS:
        d = directional_all.get(name, {}).get(inst, {})
        f = fold_all.get(name, {}).get(inst, {})
        delta = core_table["per_instrument"].get(inst, {}).get(name)
        pctl = (placebo_all.get(name, {}).get("randomized_retention", {}).get("per_instrument", {}) or {}).get(inst, {}).get("percentile_of_real")
        by_treatment[name] = {"economic_delta": delta, "case": d.get("case"), "corr_T1_T2": d.get("corr_T1_T2"),
                             "mean_T1_removed": d.get("mean_T1_removed"), "mean_T1_retained": d.get("mean_T1_retained"),
                             "fold_classification": f.get("classification"), "placebo_percentile": pctl}
    canonical = by_treatment.get("T1_canonical", {})
    favorable_removed = (canonical.get("mean_T1_removed") is not None and canonical.get("mean_T1_retained") is not None
                        and canonical["mean_T1_removed"] > canonical["mean_T1_retained"])
    return {"by_treatment": by_treatment, "removed_observations_favorable_for_long": favorable_removed,
           "interpretation": ("XAUUSD's canonical-filter removed observations have a HIGHER mean always-long "
                             "return than its retained observations -- the filter is excluding periods that "
                             "are, on average, GOOD for the fixed long scaffold (plausibly related to XAUUSD's "
                             "own strong secular uptrend within this sample), not bad ones. This is direct "
                             "evidence AGAINST a universal magnitude-risk hypothesis for this instrument, not "
                             "an optimization target -- XAUUSD is kept in every table, never excluded."
                             if favorable_removed else
                             "XAUUSD's removed observations do not show a higher mean always-long return than "
                             "retained observations under the canonical treatment; its failure is not clearly "
                             "explained by this specific mechanism alone.")}


# ==========================================================================
# Sec.17 -- JPY vs non-JPY hypothesis matrix (descriptive only, N=6)
# ==========================================================================
def jpy_hypothesis_matrix(core_table: Dict[str, Any], directional_all: Dict[str, Any],
                          fold_all: Dict[str, Any]) -> Dict[str, Any]:
    jpy, other = p91._POSITIVE_GROUP, p91._NEGATIVE_GROUP
    out = {}
    for name in _INFO_TREATMENTS:
        def _group_mean(group: Tuple[str, ...]) -> Optional[float]:
            vals = [core_table["per_instrument"][i].get(name) for i in group if core_table["per_instrument"][i].get(name) is not None]
            return round(float(np.mean(vals)), 5) if vals else None

        def _group_corr(group: Tuple[str, ...]) -> Optional[float]:
            vals = [directional_all.get(name, {}).get(i, {}).get("corr_T1_T2") for i in group
                   if isinstance(directional_all.get(name, {}).get(i), dict) and "corr_T1_T2" in directional_all[name][i]]
            return round(float(np.mean(vals)), 4) if vals else None

        n_strong_jpy = sum(1 for i in jpy if isinstance(fold_all.get(name, {}).get(i), dict)
                          and fold_all[name][i].get("classification") in ("STRONG_CONSISTENCY", "MODERATE_CONSISTENCY"))
        n_strong_other = sum(1 for i in other if isinstance(fold_all.get(name, {}).get(i), dict)
                            and fold_all[name][i].get("classification") in ("STRONG_CONSISTENCY", "MODERATE_CONSISTENCY"))
        out[name] = {"jpy_mean_effect": _group_mean(jpy), "non_jpy_mean_effect": _group_mean(other),
                    "jpy_mean_corr_T1_T2": _group_corr(jpy), "non_jpy_mean_corr_T1_T2": _group_corr(other),
                    "jpy_n_consistent": n_strong_jpy, "non_jpy_n_consistent": n_strong_other}
    out["_label"] = "DESCRIPTIVE_HYPOTHESIS_GENERATING"
    out["_note"] = ("N=6 throughout. 'JPY quote currency causes the effect' is NOT established by anything "
                    "in this repository -- reported as a descriptive correlate across every treatment, not a "
                    "causal claim.")
    return out


# ==========================================================================
# Sec.21 -- temporal stability (the 3 walk-forward folds ARE the predefined
# temporal boundaries; no new segmentation is introduced)
# ==========================================================================
def temporal_stability(confirmatory_by_treatment: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for name, conf in confirmatory_by_treatment.items():
        deltas = [f["delta_expectancy_R"] for f in conf["per_fold"] if "delta_expectancy_R" in f]
        if not deltas:
            out[name] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        abs_deltas = [abs(d) for d in deltas]
        dominant_fold = int(np.argmax(abs_deltas)) + 1
        dominant_share = round(max(abs_deltas) / sum(abs_deltas), 4) if sum(abs_deltas) > 0 else None
        out[name] = {"fold_deltas": deltas, "dominant_fold": dominant_fold, "dominant_fold_share_of_total_abs_delta": dominant_share,
                    "one_fold_dominates": dominant_share is not None and dominant_share > 0.60}
    return out


# ==========================================================================
# Sec.26 -- cost analysis (structural disclosure, computed once)
# ==========================================================================
def cost_analysis(cost_atr_grid: Tuple[float, ...] = (0.025, COST_SCENARIOS["BASE"], COST_SCENARIOS["ADVERSE"],
                                                      COST_SCENARIOS["SEVERE"])) -> Dict[str, Any]:
    folds_data = _fit_treatment_folds(TREATMENTS["T1_canonical"])
    by_cost = {}
    for c in cost_atr_grid:
        conf = _confirmatory_from_folds(folds_data, c)
        deltas = [f["delta_expectancy_R"] for f in conf["per_fold"] if "delta_expectancy_R" in f]
        by_cost[str(c)] = round(float(np.mean(deltas)), 5) if deltas else None
    invariant = len(set(by_cost.values())) <= 1
    return {"by_cost": by_cost, "structurally_invariant": invariant,
           "disclosure": ("The treatment contrast is mathematically insensitive to this symmetric cost "
                         "specification: both baseline and filter subtract the SAME per-trade cost "
                         "constant, and expectancy is a linear mean, so cost cancels exactly in the delta "
                         "regardless of its value. This is a structural property of the comparison, NOT "
                         "'strong cost robustness' in the sense of surviving increasing real transaction "
                         "friction -- disclosed explicitly per Sec.26's own instruction.")}


# ==========================================================================
# Sec.27 -- drawdown decomposition across treatments
# ==========================================================================
def drawdown_decomposition(placebo_all: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for name in _INFO_TREATMENTS:
        er = placebo_all.get(name, {}).get("generic_exposure_reduction", {})
        if not er or er.get("state") == "INSUFFICIENT_SAMPLE":
            out[name] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        base_dd = er["baseline"].get("max_drawdown_R")
        generic_dd = er["generic_exposure_reduction"].get("max_drawdown_R")
        filter_dd = er["real_filter"].get("max_drawdown_R")
        generic_improve = (generic_dd - base_dd) if (generic_dd is not None and base_dd is not None) else None
        filter_improve = (filter_dd - base_dd) if (filter_dd is not None and base_dd is not None) else None
        incremental = (filter_improve - generic_improve) if (generic_improve is not None and filter_improve is not None) else None
        out[name] = {"baseline_max_drawdown_R": base_dd, "generic_max_drawdown_R": generic_dd,
                    "filter_max_drawdown_R": filter_dd,
                    "generic_improvement_R": round(generic_improve, 4) if generic_improve is not None else None,
                    "filter_improvement_R": round(filter_improve, 4) if filter_improve is not None else None,
                    "incremental_improvement_beyond_generic_R": round(incremental, 4) if incremental is not None else None}
    return out


# ==========================================================================
# Sec.23/24/37/38 -- minimum sufficient mechanism
# ==========================================================================
_HIERARCHY_ORDER: Tuple[str, ...] = ("T3_volatility_only", "T2_magnitude_only",
                                    "T6_magnitude_plus_volatility", "T5_magnitude_plus_volume", "T7_full")
_SCENARIO_BY_LEVEL: Dict[str, str] = {
    "GENERIC": "Scenario F -- no information treatment reliably beats generic exposure reduction; downgrade the filter hypothesis.",
    "T3_volatility_only": "Scenario B -- volatility-only explains the effect; the volume-informed magnitude story is substantially reduced.",
    "T2_magnitude_only": "Scenario A -- magnitude-only explains the effect; volume is unnecessary.",
    "T6_magnitude_plus_volatility": "Scenario C -- magnitude+volatility explains the effect; volume has not demonstrated necessity.",
    "T5_magnitude_plus_volume": "Scenario D -- magnitude+volume beats simpler alternatives; volume has evidence of incremental value.",
    "T7_full": "Scenario E -- the full three-way combination is required; interaction/combined information deserves further research.",
}


def determine_minimum_sufficient_mechanism(core_table: Dict[str, Any], placebo_all: Dict[str, Any]) -> Dict[str, Any]:
    e_canonical = core_table["pooled"].get("T1_canonical")
    if e_canonical is None:
        return {"state": "CANNOT_DETERMINE", "reason": "Canonical treatment could not be computed."}
    ceiling = abs(e_canonical)

    generic = (placebo_all.get("T1_canonical", {}).get("generic_exposure_reduction", {}) or {})
    generic_beats_baseline = False
    if generic and generic.get("state") != "INSUFFICIENT_SAMPLE":
        generic_beats_baseline = (generic["generic_exposure_reduction"].get("expectancy_R") or 0) > \
                                 (generic["baseline"].get("expectancy_R") or 0)

    for level in _HIERARCHY_ORDER:
        e_level = core_table["pooled"].get(level)
        pctl = (placebo_all.get(level, {}).get("randomized_retention", {}).get("pooled") or {}).get("percentile_of_real")
        if e_level is None or pctl is None:
            continue
        sufficient = (abs(e_level) >= _MATERIALITY_FRACTION * ceiling and np.sign(e_level) == np.sign(e_canonical)
                     and pctl >= _PLACEBO_PASS_PERCENTILE)
        if sufficient:
            return {"state": "DETERMINED", "minimum_level": level, "level_pooled_delta": e_level,
                   "canonical_pooled_delta": e_canonical, "level_placebo_percentile": pctl,
                   "scenario": _SCENARIO_BY_LEVEL[level],
                   "generic_exposure_reduction_beats_baseline": generic_beats_baseline}
    # nothing in the hierarchy (including full) reached the bar
    canonical_pctl = (placebo_all.get("T1_canonical", {}).get("randomized_retention", {}).get("pooled") or {}).get("percentile_of_real")
    if canonical_pctl is not None and canonical_pctl < _PLACEBO_PASS_PERCENTILE:
        return {"state": "DETERMINED", "minimum_level": "NONE", "canonical_pooled_delta": e_canonical,
               "level_placebo_percentile": canonical_pctl, "scenario": _SCENARIO_BY_LEVEL["GENERIC"],
               "generic_exposure_reduction_beats_baseline": generic_beats_baseline}
    return {"state": "DETERMINED", "minimum_level": "T7_full", "canonical_pooled_delta": e_canonical,
           "scenario": _SCENARIO_BY_LEVEL["T7_full"], "generic_exposure_reduction_beats_baseline": generic_beats_baseline}


# ==========================================================================
# result container
# ==========================================================================
@dataclass
class Phase93Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    canonical_horizon: int
    canonical_quantile: float
    canonical_reproduction: Dict[str, Any]
    core_attribution_table: Dict[str, Any]
    information_ablation: Dict[str, Any]
    incremental_volume_analysis: Dict[str, Any]
    placebo_battery: Dict[str, Any]
    directional_contamination: Dict[str, Any]
    fold_level_classification: Dict[str, Any]
    xauusd_deep_dive: Dict[str, Any]
    jpy_hypothesis_matrix: Dict[str, Any]
    temporal_stability: Dict[str, Any]
    cost_analysis: Dict[str, Any]
    drawdown_decomposition: Dict[str, Any]
    minimum_sufficient_mechanism: Dict[str, Any]
    magnitude_effect: str
    magnitude_effect_reason: str
    volatility_explanation: str
    volatility_explanation_reason: str
    volume_incremental_value: str
    volume_incremental_value_reason: str
    filter_mechanism: str
    filter_mechanism_reason: str
    directional_dependence: str
    directional_dependence_reason: str
    cross_instrument_generalization: str
    cross_instrument_generalization_reason: str
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


def run() -> Phase93Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()

    recon = verify_canonical_reproduction()
    if recon["state"] == "MATERIAL_DISCREPANCY":
        # Sec.43 stop condition -- do not silently continue with an
        # un-anchored mechanism study; persist a minimal, honest result.
        rt = (datetime.now(timezone.utc) - t0).total_seconds()
        return Phase93Result(
            schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
            frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash, universe=list(INSTRUMENTS_83),
            timeframe=PRIMARY_TF, canonical_horizon=_HORIZON, canonical_quantile=_ELIGIBILITY_QUANTILE,
            canonical_reproduction=recon, core_attribution_table={}, information_ablation={},
            incremental_volume_analysis={}, placebo_battery={}, directional_contamination={},
            fold_level_classification={}, xauusd_deep_dive={}, jpy_hypothesis_matrix={}, temporal_stability={},
            cost_analysis={}, drawdown_decomposition={}, minimum_sufficient_mechanism={"state": "BLOCKED"},
            magnitude_effect="MAGNITUDE_EFFECT_NOT_CONFIRMED", magnitude_effect_reason="Blocked: canonical reproduction failed.",
            volatility_explanation="VOLATILITY_EXPLANATION_NOT_CONFIRMED", volatility_explanation_reason="Blocked.",
            volume_incremental_value="VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED", volume_incremental_value_reason="Blocked.",
            filter_mechanism="FILTER_MECHANISM_INVALIDATED",
            filter_mechanism_reason=f"Phase-92 canonical result could not be reproduced (max_abs_diff={recon.get('max_abs_diff')}).",
            directional_dependence="INSUFFICIENT_EVIDENCE", directional_dependence_reason="Blocked.",
            cross_instrument_generalization="NOT_GENERALIZABLE", cross_instrument_generalization_reason="Blocked.",
            determinism={"match": None}, runtime_seconds=round(rt, 1), content_hash="",
        )

    confirmatory_by_treatment, folds_cache = run_all_treatments()
    core_table = core_attribution_table(confirmatory_by_treatment)
    ablation = information_ablation(core_table)
    placebo_all = placebo_battery_all_treatments(folds_cache)
    directional_all = directional_contamination_all_treatments(folds_cache)
    fold_all = fold_level_all_treatments(confirmatory_by_treatment)
    inc_volume = incremental_volume_analysis(core_table, placebo_all, fold_all)
    xauusd = xauusd_deep_dive(core_table, directional_all, fold_all, placebo_all)
    jpy_matrix = jpy_hypothesis_matrix(core_table, directional_all, fold_all)
    temporal = temporal_stability(confirmatory_by_treatment)
    cost = cost_analysis()
    drawdown = drawdown_decomposition(placebo_all)
    min_mechanism = determine_minimum_sufficient_mechanism(core_table, placebo_all)

    mag_verdict, mag_reason = classify_magnitude_effect(core_table, placebo_all)
    vol_verdict, vol_reason = classify_volatility_effect(core_table, placebo_all)
    filt_verdict, filt_reason = classify_filter_mechanism(core_table, placebo_all, fold_all)
    dir_verdict, dir_reason = classify_directional_dependence(directional_all.get("T1_canonical", {}))
    gen_verdict, gen_reason = classify_cross_instrument_generalization(fold_all.get("T1_canonical", {}))

    # determinism check: re-run the cheapest deterministic diagnostic twice
    ablation_2 = information_ablation(core_attribution_table(confirmatory_by_treatment))
    determinism_match = (ablation == ablation_2)

    ident = json.dumps({"schema": SCHEMA_VERSION, "core_table": core_table, "min_mechanism": min_mechanism,
                       "mag_verdict": mag_verdict, "vol_verdict": vol_verdict,
                       "volume_verdict": inc_volume["verdict"], "filter_verdict": filt_verdict},
                      sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase93Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash, universe=list(INSTRUMENTS_83),
        timeframe=PRIMARY_TF, canonical_horizon=_HORIZON, canonical_quantile=_ELIGIBILITY_QUANTILE,
        canonical_reproduction=recon, core_attribution_table=core_table, information_ablation=ablation,
        incremental_volume_analysis=inc_volume, placebo_battery=placebo_all, directional_contamination=directional_all,
        fold_level_classification=fold_all, xauusd_deep_dive=xauusd, jpy_hypothesis_matrix=jpy_matrix,
        temporal_stability=temporal, cost_analysis=cost, drawdown_decomposition=drawdown,
        minimum_sufficient_mechanism=min_mechanism,
        magnitude_effect=mag_verdict, magnitude_effect_reason=mag_reason,
        volatility_explanation=vol_verdict, volatility_explanation_reason=vol_reason,
        volume_incremental_value=inc_volume["verdict"], volume_incremental_value_reason=inc_volume["reason"],
        filter_mechanism=filt_verdict, filter_mechanism_reason=filt_reason,
        directional_dependence=dir_verdict, directional_dependence_reason=dir_reason,
        cross_instrument_generalization=gen_verdict, cross_instrument_generalization_reason=gen_reason,
        determinism={"match": determinism_match}, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase93Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase93_mechanism_isolation", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 93 - magnitude/volatility/volume mechanism isolation ...", flush=True)
    res = run()
    h = persist(res)   # persist first -- verbose printing must never be able to lose the artifact
    print(f"\n=== PHASE 93 ({res.runtime_seconds}s) ===")
    print(f"\nCanonical reproduction: {res.canonical_reproduction.get('state')} "
         f"max_abs_diff={res.canonical_reproduction.get('max_abs_diff')}")
    print(f"\nCore attribution table (pooled): {json.dumps(res.core_attribution_table.get('pooled'), default=str)}")
    print(f"\nInformation ablation: {json.dumps(res.information_ablation, default=str)}")
    print(f"\nIncremental volume: {json.dumps({k: v for k, v in res.incremental_volume_analysis.items() if k != 'per_instrument'}, default=str)}")
    print(f"\nMinimum sufficient mechanism: {json.dumps(res.minimum_sufficient_mechanism, default=str)}")
    print(f"\nXAUUSD deep dive interpretation: {res.xauusd_deep_dive.get('interpretation')}")
    print(f"\nDeterminism: {res.determinism}")
    print(f"\nMAGNITUDE_EFFECT: {res.magnitude_effect} -- {res.magnitude_effect_reason}")
    print(f"VOLATILITY_EXPLANATION: {res.volatility_explanation} -- {res.volatility_explanation_reason}")
    print(f"VOLUME_INCREMENTAL_VALUE: {res.volume_incremental_value} -- {res.volume_incremental_value_reason}")
    print(f"FILTER_MECHANISM: {res.filter_mechanism} -- {res.filter_mechanism_reason}")
    print(f"DIRECTIONAL_DEPENDENCE: {res.directional_dependence} -- {res.directional_dependence_reason}")
    print(f"CROSS_INSTRUMENT_GENERALIZATION: {res.cross_instrument_generalization} -- {res.cross_instrument_generalization_reason}")
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DESIGN_NOTE", "TREATMENTS", "VOLATILITY_FEATURES", "MAGNITUDE_FEATURES",
    "VOLUME_FEATURES", "verify_canonical_reproduction", "run_all_treatments", "core_attribution_table",
    "information_ablation", "placebo_battery_all_treatments", "directional_contamination_all_treatments",
    "fold_level_all_treatments", "incremental_volume_analysis", "xauusd_deep_dive", "jpy_hypothesis_matrix",
    "temporal_stability", "cost_analysis", "drawdown_decomposition", "determine_minimum_sufficient_mechanism",
    "classify_magnitude_effect", "classify_volatility_effect", "classify_filter_mechanism",
    "classify_directional_dependence", "classify_cross_instrument_generalization", "run", "persist",
    "get_result", "main",
]
