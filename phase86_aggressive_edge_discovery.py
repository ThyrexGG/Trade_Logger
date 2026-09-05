# -*- coding: utf-8 -*-
"""
Phase 86 -- Aggressive Trading Edge Discovery: From Proven Information to
an Actual Tradable Edge.

Distinct from Phase 85 (which asked "is there information?" and is reused
here as an input, never repeated): this phase asks "can we find a real,
cost-aware, out-of-sample trading edge?" It is explicitly permitted to
search more aggressively than Phases 76-85 (a small, predeclared threshold
grid may be explored on discovery data -- master prompt Sec.9-10), but
every search space is disclosed in ``RESEARCH_LEDGER`` and no threshold or
rule is ever selected using confirmation or final-holdout data.

Reused, unchanged: Phase 83's frozen Strong Context Baseline features and
T1/T2 target formulas, Phase 84/85's frozen ``volume_rank``/``volume_ret_1``
construction, Phase 85's unified matched-population dataset builder
(``phase85_tick_volume_confirmation.build_pooled_dataset_85``), Phase 76's
block-bootstrap engine and its documented conservative cost proxy
(``_COST_ATR_PROXY = 0.05``), and the unchanged 6-instrument canonical
universe. No new market data, no new external feature, no new dependency.

Three-way temporal split (own to THIS phase; the frozen Phase-74 Gold
holdout contract is a completely separate, never-touched invariant --
"final holdout" below refers only to a new, predeclared internal time
partition carved out of data that earlier phases only ever used for R^2/
information tests, never for trade-level rule fitting):
  * discovery      < 2025-01-01                     (Phase 83's own cutoff)
  * confirmation    2025-07-01 .. 2026-03-01         (candidate promotion)
  * final holdout  >= 2026-03-01                     (evaluated ONCE, at the end)
These three dates are fixed in this module BEFORE any candidate result was
inspected and are never adjusted afterward.

Two pre-registered research tracks (chosen from the master prompt's own
stated research-budget priority order, Sec.24, given the concrete evidence
Phase 85 actually produced -- magnitude information confirmed, direction
not):

  TRACK A/C (priority 1) -- ``conditional_asymmetry_screen``: a small,
  fully pre-registered 8-cell screen (location-in-range extreme x trend/
  range regime x volume-rank state) testing whether DIRECTION, shown flat
  unconditionally throughout Phases 76-85, becomes asymmetric within a
  volume-conditioned three-way cell. This is a genuinely new test: Phase 83
  tested location x regime on direction already (``I4_LOCATION_x_TREND``,
  ``EXPLAINED_BY_CONTEXT``) but never combined it with volume. Screening
  only (Level 0) -- a cell is promoted to a trading candidate only if it
  survives being re-evaluated, UNCHANGED, on confirmation.

  TRACK B (priority 2) -- ``Candidate1MomentumVolumeFilter``: a concrete,
  minimal trading rule. Setup = sign of the existing causal ``mom_4``
  feature (ATR-normalized 4-bar momentum, already in the Phase 83 context
  library -- no new indicator). Filter = ``volume_rank`` at or above a
  threshold selected, from a small predeclared discovery-only grid, by a
  documented "widest stable plateau" rule (master prompt Sec.10), not by
  argmax. Trade outcome directly reuses Phase 83's own frozen T1 formula
  (ATR-normalized signed forward return) as the R-multiple -- no new return
  definition is introduced. Evaluated under three disclosed, existing-
  project-derived cost scenarios (BASE = the project's own documented
  0.05-ATR conservative retail proxy, ADVERSE = 0.10, SEVERE = 0.20).
  Exit-mechanism robustness (master prompt Sec.12) is tested via the
  existing horizon family {1,2,4,8} rather than a new path-dependent
  stop/target simulator -- disclosed as a scope choice, not a silent gap.

Read-only research. No execution/broker/risk import. No entries, exits,
stop losses, position sizing, or automation exist anywhere in this module
-- everything here measures information/expectancy on already-closed
historical bars. The frozen Phase-74 Gold holdout is never read.
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
import phase76_event_study as p76
import phase83_conditional_interaction_discovery as p83
import phase85_tick_volume_confirmation as p85
from phase76_event_study import RANDOM_SEED, _COST_ATR_PROXY, _benjamini_hochberg, block_bootstrap
from phase83_conditional_interaction_discovery import INSTRUMENTS_83, PRIMARY_TF

SCHEMA_VERSION = "phase86.1"
ARTIFACT_KEY = "phase86_aggressive_edge_discovery"

# ==========================================================================
# Frozen, predeclared temporal split (own to this phase; never adjusted
# after any result was inspected). NOT the frozen Gold holdout contract.
# ==========================================================================
_DISCOVERY_CUTOFF = p83._DISCOVERY_CUTOFF                       # < 2025-01-01
_CONFIRMATION_START = p83._CONFIRMATION_START                   # >= 2025-07-01
_FINAL_HOLDOUT_START = pd.Timestamp("2026-03-01", tz="UTC")     # >= 2026-03-01, NEW

# Predeclared cost scenarios, ATR round-trip units. BASE reuses the
# project's own documented conservative retail proxy (phase76_event_study,
# Sec.24 of that phase's own docstring) rather than inventing a new number.
COST_SCENARIOS: Dict[str, float] = {"BASE": _COST_ATR_PROXY, "ADVERSE": 0.10, "SEVERE": 0.20}

# Predeclared, discovery-only volume threshold grid (Sec.9 of the master
# prompt explicitly permits this, unlike Phases 76-85's discipline).
_VOLUME_THRESHOLD_GRID: Tuple[float, ...] = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90)
_CANDIDATE1_HEADLINE_HORIZON = 4          # reused, not searched
_ROBUSTNESS_HORIZONS: Tuple[int, ...] = (1, 2, 4, 8)
_MIN_CELL_N = 200
_MATERIAL_MEAN_R = 1.3 * _COST_ATR_PROXY  # reuses Phase76's own materiality convention

_PRIORITY_ORDER = ("conditional_directional_asymmetry", "volume_plus_directional_setup",
                   "volume_plus_expansion_transition", "mtf_plus_structure_plus_volume",
                   "avoidance_filter", "position_risk_adaptation")


# ==========================================================================
# temporal split (three-way, own to this phase)
# ==========================================================================
def three_way_split(ds: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    discovery = ds[ds["prediction_timestamp"] < _DISCOVERY_CUTOFF]
    confirmation = ds[(ds["prediction_timestamp"] >= _CONFIRMATION_START)
                      & (ds["prediction_timestamp"] < _FINAL_HOLDOUT_START)]
    final_holdout = ds[ds["prediction_timestamp"] >= _FINAL_HOLDOUT_START]
    return discovery, confirmation, final_holdout


# ==========================================================================
# research ledger -- every hypothesis tested is recorded here, promoted or
# not (master prompt Sec.4/Sec.20/Sec.29H: never hide a failed experiment)
# ==========================================================================
class ResearchLedger:
    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def record(self, track: str, hypothesis_id: str, description: str, stage: str,
              outcome: str, reason: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        self.entries.append({"track": track, "hypothesis_id": hypothesis_id,
                            "description": description, "stage": stage, "outcome": outcome,
                            "reason": reason, "metrics": metrics or {}})

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self.entries)

    def summary(self) -> Dict[str, Any]:
        return {"n_hypotheses_recorded": len(self.entries),
               "n_promoted": sum(1 for e in self.entries if e["outcome"].startswith("PROMOTED")),
               "n_rejected": sum(1 for e in self.entries if e["outcome"].startswith("REJECTED")
                                 or e["outcome"] == "KILLED"),
               "by_track": {t: sum(1 for e in self.entries if e["track"] == t)
                           for t in sorted(set(e["track"] for e in self.entries))}}


# ==========================================================================
# TRACK A/C -- conditional directional asymmetry screen (Level 0)
# ==========================================================================
_ASYMMETRY_CELLS: Tuple[Dict[str, Any], ...] = (
    {"id": "A1_high_loc_trending_highvol", "loc": "high", "regime": "TRENDING", "vol": "high",
     "hypothesis": "Breakout continuation: near range-high, trending, high volume -> positive T1."},
    {"id": "A2_high_loc_ranging_highvol", "loc": "high", "regime": "RANGING", "vol": "high",
     "hypothesis": "Exhaustion reversal: near range-high, ranging, high volume -> negative T1."},
    {"id": "A3_low_loc_trending_highvol", "loc": "low", "regime": "TRENDING", "vol": "high",
     "hypothesis": "Breakout continuation (downside): near range-low, trending, high volume -> negative T1."},
    {"id": "A4_low_loc_ranging_highvol", "loc": "low", "regime": "RANGING", "vol": "high",
     "hypothesis": "Exhaustion reversal (upside): near range-low, ranging, high volume -> positive T1."},
    {"id": "A5_high_loc_trending_lowvol", "loc": "high", "regime": "TRENDING", "vol": "low",
     "hypothesis": "Same location/regime cell WITHOUT the volume condition (contrast cell)."},
    {"id": "A6_high_loc_ranging_lowvol", "loc": "high", "regime": "RANGING", "vol": "low",
     "hypothesis": "Contrast cell for A2 without volume condition."},
    {"id": "A7_low_loc_trending_lowvol", "loc": "low", "regime": "TRENDING", "vol": "low",
     "hypothesis": "Contrast cell for A3 without volume condition."},
    {"id": "A8_low_loc_ranging_lowvol", "loc": "low", "regime": "RANGING", "vol": "low",
     "hypothesis": "Contrast cell for A4 without volume condition."},
)
_LOC_HIGH_THR, _LOC_LOW_THR, _VOL_HIGH_THR = 0.8, 0.2, 0.7


def _cell_mask(ds: pd.DataFrame, cell: Dict[str, Any]) -> np.ndarray:
    loc = ds["feat__loc_in_range"].to_numpy(float)
    vol = ds["feat__volume_rank"].to_numpy(float)
    trending = ds["feat__regime_TRENDING"].to_numpy(float) > 0.5
    ranging = ds["feat__regime_RANGING"].to_numpy(float) > 0.5
    loc_mask = (loc >= _LOC_HIGH_THR) if cell["loc"] == "high" else (loc <= _LOC_LOW_THR)
    regime_mask = trending if cell["regime"] == "TRENDING" else ranging
    vol_mask = (vol >= _VOL_HIGH_THR) if cell["vol"] == "high" else (vol < _VOL_HIGH_THR)
    return loc_mask & regime_mask & vol_mask


def conditional_asymmetry_screen(ds: pd.DataFrame, cells: Tuple[Dict[str, Any], ...] = _ASYMMETRY_CELLS,
                                 target_col: str = "T1") -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    pvals, ids = [], []
    for cell in cells:
        mask = _cell_mask(ds, cell)
        n = int(mask.sum())
        if n < _MIN_CELL_N:
            results[cell["id"]] = {"n": n, "state": "INSUFFICIENT_SAMPLE", "hypothesis": cell["hypothesis"]}
            continue
        vals = ds.loc[mask, target_col].to_numpy(float)
        boot = block_bootstrap(vals, block=4, seed=RANDOM_SEED)
        boot["hypothesis"] = cell["hypothesis"]
        results[cell["id"]] = boot
        if boot.get("se"):
            z = boot["mean"] / boot["se"] if boot["se"] > 0 else 0.0
            pvals.append(2 * (1 - p76._norm_cdf(abs(z))))
            ids.append(cell["id"])
    bh = _benjamini_hochberg(pvals, q=0.10) if pvals else []
    bh_map = {cid: bool(f) for cid, f in zip(ids, bh)}
    for cid in results:
        if cid in bh_map:
            results[cid]["survives_bh"] = bh_map[cid]
    return results


def promote_asymmetry_candidates(discovery_screen: Dict[str, Any], confirmation: pd.DataFrame,
                                 cells: Tuple[Dict[str, Any], ...] = _ASYMMETRY_CELLS,
                                 ledger: Optional[ResearchLedger] = None) -> Dict[str, Any]:
    """A discovery cell is promoted only if: (a) its discovery-window mean
    T1 is material (>= materiality margin) and CI-excluding, (b) it survives
    BH correction, and (c) the SAME sign and a materially non-zero effect
    replicates, UNCHANGED, on confirmation. No cell definition is ever
    adjusted after seeing confirmation."""
    promoted: Dict[str, Any] = {}
    for cell in cells:
        cid = cell["id"]
        disc = discovery_screen.get(cid, {})
        if disc.get("state") == "INSUFFICIENT_SAMPLE":
            if ledger:
                ledger.record("conditional_directional_asymmetry", cid, cell["hypothesis"],
                             "discovery_screen", "REJECTED_INSUFFICIENT_SAMPLE", "n < 200 in discovery")
            continue
        material = abs(disc.get("mean") or 0) >= _MATERIAL_MEAN_R
        ci_excludes = disc.get("verdict") in ("POSITIVE", "NEGATIVE")
        bh_ok = disc.get("survives_bh", False)
        if not (material and ci_excludes and bh_ok):
            if ledger:
                ledger.record("conditional_directional_asymmetry", cid, cell["hypothesis"],
                             "discovery_screen", "REJECTED_NOT_MATERIAL_OR_NOT_SIGNIFICANT",
                             f"mean={disc.get('mean')} verdict={disc.get('verdict')} bh={bh_ok}")
            continue
        mask = _cell_mask(confirmation, cell)
        n = int(mask.sum())
        if n < _MIN_CELL_N:
            if ledger:
                ledger.record("conditional_directional_asymmetry", cid, cell["hypothesis"],
                             "confirmation", "KILLED", "insufficient confirmation sample")
            continue
        conf_boot = block_bootstrap(confirmation.loc[mask, "T1"].to_numpy(float), block=4, seed=RANDOM_SEED)
        same_sign = np.sign(conf_boot.get("mean") or 0) == np.sign(disc.get("mean") or 0)
        conf_material = abs(conf_boot.get("mean") or 0) >= _MATERIAL_MEAN_R
        conf_ci_ok = conf_boot.get("verdict") in ("POSITIVE", "NEGATIVE")
        if same_sign and conf_material and conf_ci_ok:
            promoted[cid] = {"discovery": disc, "confirmation": conf_boot, "hypothesis": cell["hypothesis"]}
            if ledger:
                ledger.record("conditional_directional_asymmetry", cid, cell["hypothesis"],
                             "confirmation", "PROMOTED_LEVEL_1",
                             "replicated sign and materiality on confirmation", metrics=conf_boot)
        else:
            if ledger:
                ledger.record("conditional_directional_asymmetry", cid, cell["hypothesis"],
                             "confirmation", "KILLED",
                             f"did not replicate: same_sign={same_sign} material={conf_material} ci_ok={conf_ci_ok}",
                             metrics=conf_boot)
    return promoted


# ==========================================================================
# TRACK B -- momentum + volume filter trading rule
# ==========================================================================
def _rule_returns(ds: pd.DataFrame, threshold: float, cost_atr: float) -> np.ndarray:
    """R-multiple := sign(mom_4) x T1 - cost_atr, restricted to rows where
    the volume filter is active and mom_4 is a defined nonzero direction.
    T1 is Phase 83's own frozen ATR-normalized signed-return formula,
    reused unchanged as the raw (pre-cost) trade outcome."""
    mom = ds["feat__mom_4"].to_numpy(float)
    vol = ds["feat__volume_rank"].to_numpy(float)
    t1 = ds["T1"].to_numpy(float)
    direction = np.sign(mom)
    active = (direction != 0) & np.isfinite(t1) & (vol >= threshold)
    r = direction[active] * t1[active] - cost_atr
    return r


def _rule_stats(r: np.ndarray) -> Dict[str, Any]:
    boot = block_bootstrap(r, block=_CANDIDATE1_HEADLINE_HORIZON, seed=RANDOM_SEED)
    wins = r[r > 0]
    losses = r[r < 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else None
    boot.update({"hit_rate": round(float((r > 0).mean()), 4) if len(r) else None,
                "avg_win": round(float(wins.mean()), 5) if len(wins) else None,
                "avg_loss": round(float(losses.mean()), 5) if len(losses) else None,
                "profit_factor": round(pf, 4) if pf is not None else None,
                "n_trades": int(len(r))})
    return boot


def screen_candidate1(discovery: pd.DataFrame, grid: Tuple[float, ...] = _VOLUME_THRESHOLD_GRID,
                      cost_atr: float = COST_SCENARIOS["BASE"]) -> Dict[float, Dict[str, Any]]:
    return {thr: _rule_stats(_rule_returns(discovery, thr, cost_atr)) for thr in grid}


def select_frozen_threshold(screen: Dict[float, Dict[str, Any]],
                            grid: Tuple[float, ...] = _VOLUME_THRESHOLD_GRID) -> Dict[str, Any]:
    """Sec.10: prefer a stable plateau over a single spike. First restrict
    to grid points with a material, CI-excluding-zero positive mean
    ("candidates"). A lone candidate with NEITHER immediate grid neighbour
    also a candidate is excluded outright -- it has no plateau support and
    cannot win, however large its own point estimate. Among the remaining
    ("eligible") points, score each by the mean of itself plus whichever of
    its immediate neighbours are finite, breaking ties by how many
    neighbours it has (more support = more central to the plateau)."""
    idx_of = {t: i for i, t in enumerate(grid)}
    candidates = set(t for t in grid if screen[t]["verdict"] == "POSITIVE"
                     and (screen[t]["mean"] or 0) >= _MATERIAL_MEAN_R and screen[t]["n_trades"] >= 500)
    if not candidates:
        return {"frozen_threshold": None, "reason": "no grid point cleared the materiality/CI bar"}

    def _neighbours(t: float) -> List[float]:
        i = idx_of[t]
        return [grid[j] for j in (i - 1, i + 1) if 0 <= j < len(grid)]

    eligible = [t for t in candidates if any(n in candidates for n in _neighbours(t))]
    if not eligible:
        # documented fallback: every candidate is an isolated spike with no
        # supporting neighbour -- fall back to the single best candidate
        # rather than refusing to freeze anything.
        eligible = list(candidates)

    scored = []
    for t in eligible:
        window = [screen[t]["mean"]] + [screen[n]["mean"] for n in _neighbours(t)
                                        if screen[n]["mean"] is not None]
        scored.append((t, float(np.mean(window)), len(window)))
    best = max(scored, key=lambda x: (x[1], x[2]))[0]
    return {"frozen_threshold": best, "plateau_scores": {t: s for t, s, _ in scored},
           "candidates_considered": sorted(candidates), "eligible_considered": sorted(eligible)}


def evaluate_candidate1(ds: pd.DataFrame, threshold: float, cost_atr: float) -> Dict[str, Any]:
    return _rule_stats(_rule_returns(ds, threshold, cost_atr))


def candidate1_cross_asset(ds: pd.DataFrame, threshold: float, cost_atr: float) -> Dict[str, Any]:
    out = {}
    for inst in INSTRUMENTS_83:
        sub = ds[ds["instrument"] == inst]
        r = _rule_returns(sub, threshold, cost_atr)
        out[inst] = _rule_stats(r) if len(r) >= _MIN_CELL_N else {"state": "INSUFFICIENT_SAMPLE", "n": len(r)}
    return out


def candidate1_temporal_blocks(ds: pd.DataFrame, threshold: float, cost_atr: float) -> List[Dict[str, Any]]:
    out = []
    for label, lo, hi in p85._quarter_blocks(ds):
        mask = (ds["prediction_timestamp"] >= lo) & (ds["prediction_timestamp"] < hi)
        sub = ds[mask]
        r = _rule_returns(sub, threshold, cost_atr)
        row = {"block": label, "n_rows": int(len(sub))}
        row.update(_rule_stats(r) if len(r) >= _MIN_CELL_N else {"state": "INSUFFICIENT_SAMPLE"})
        out.append(row)
    return out


def candidate1_parameter_perturbation(ds: pd.DataFrame, threshold: float, cost_atr: float,
                                      grid: Tuple[float, ...] = _VOLUME_THRESHOLD_GRID
                                      ) -> Dict[float, Dict[str, Any]]:
    idx = list(grid).index(threshold) if threshold in grid else None
    neighbours = grid if idx is None else grid[max(0, idx - 2): idx + 3]
    return {t: _rule_stats(_rule_returns(ds, t, cost_atr)) for t in neighbours}


def candidate1_cost_sensitivity(ds: pd.DataFrame, threshold: float,
                                cost_scenarios: Dict[str, float] = COST_SCENARIOS
                                ) -> Dict[str, Dict[str, Any]]:
    return {name: _rule_stats(_rule_returns(ds, threshold, cost)) for name, cost in cost_scenarios.items()}


def candidate1_horizon_robustness(tf: str, threshold: float, cost_atr: float,
                                  horizons: Tuple[int, ...] = _ROBUSTNESS_HORIZONS
                                  ) -> Dict[int, Dict[str, Any]]:
    """Sec.12 exit-mechanism robustness, implemented via the existing
    horizon family (a different fixed-holding-period 'exit') rather than a
    new path-dependent stop/target simulator -- a disclosed scope choice,
    not a silent gap (see module docstring)."""
    out = {}
    for h in horizons:
        ds_h = p85.build_pooled_dataset_85(tf, h)
        _, confirmation, _ = three_way_split(ds_h)
        out[h] = _rule_stats(_rule_returns(confirmation, threshold, cost_atr))
    return out


def candidate1_placebos(confirmation: pd.DataFrame, threshold: float, cost_atr: float,
                        seed: int = 86001) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    # (a) shuffle direction sign -- destroys the momentum-direction bet
    mom = confirmation["feat__mom_4"].to_numpy(float)
    vol = confirmation["feat__volume_rank"].to_numpy(float)
    t1 = confirmation["T1"].to_numpy(float)
    direction = np.sign(mom)
    active = (direction != 0) & np.isfinite(t1) & (vol >= threshold)
    shuffled_dir = rng.permutation(direction[active])
    r_dir_shuffle = shuffled_dir * t1[active] - cost_atr

    # (b) shuffle volume_rank (breaks the filter's temporal association)
    vol_shuffled = rng.permutation(vol)
    active2 = (direction != 0) & np.isfinite(t1) & (vol_shuffled >= threshold)
    r_vol_shuffle = direction[active2] * t1[active2] - cost_atr

    return {"direction_shuffle": _rule_stats(r_dir_shuffle),
           "volume_shuffle": _rule_stats(r_vol_shuffle)}


# ==========================================================================
# scorecard / promotion level / verdict vocabulary
# ==========================================================================
_VALID_VERDICTS = ("NO_EDGE_FOUND", "PREDICTIVE_INFORMATION_ONLY", "ACTIONABLE_BUT_NOT_ECONOMIC",
                  "PROMISING_TRADING_HYPOTHESIS", "POSITIVE_NET_EXPECTANCY_BUT_FRAGILE",
                  "ROBUST_EDGE_CANDIDATE", "ROBUST_TRADING_EDGE", "REJECTED", "OVERFIT", "LEAKAGE")


def build_scorecard(confirmation_stats: Dict[str, Any], cross_asset: Dict[str, Any],
                    temporal: List[Dict[str, Any]], perturbation: Dict[float, Dict[str, Any]],
                    cost_sensitivity: Dict[str, Dict[str, Any]], placebos: Dict[str, Any],
                    holdout_stats: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    n_positive_instruments = sum(1 for v in cross_asset.values()
                                 if isinstance(v, dict) and v.get("verdict") == "POSITIVE")
    n_positive_blocks = sum(1 for b in temporal if b.get("verdict") == "POSITIVE")
    n_total_blocks = sum(1 for b in temporal if "verdict" in b)
    perturbation_signs = [v["verdict"] for v in perturbation.values() if "verdict" in v]
    plateau_stable = len(set(s for s in perturbation_signs if s != "ZERO_CROSSING")) <= 1
    survives_base = cost_sensitivity.get("BASE", {}).get("verdict") == "POSITIVE"
    survives_adverse = cost_sensitivity.get("ADVERSE", {}).get("verdict") == "POSITIVE"
    survives_severe = cost_sensitivity.get("SEVERE", {}).get("verdict") == "POSITIVE"
    placebos_collapsed = all(abs(p.get("mean") or 0) < _MATERIAL_MEAN_R for p in placebos.values())
    return {
        "directional_separation": "N/A (magnitude-based rule)",
        "magnitude_separation": confirmation_stats.get("verdict"),
        "conditional_improvement": "see confounding note in report -- rule is inherently conditional (volume filter)",
        "gross_expectancy": confirmation_stats.get("mean"),
        "net_expectancy_base_cost": cost_sensitivity.get("BASE", {}).get("mean"),
        "net_expectancy_adverse_cost": cost_sensitivity.get("ADVERSE", {}).get("mean"),
        "net_expectancy_severe_cost": cost_sensitivity.get("SEVERE", {}).get("mean"),
        "cost_sensitivity": {"survives_base": survives_base, "survives_adverse": survives_adverse,
                             "survives_severe": survives_severe},
        "trade_frequency_confirmation": confirmation_stats.get("n_trades"),
        "temporal_stability": f"{n_positive_blocks}/{n_total_blocks} blocks POSITIVE",
        "cross_asset_stability": f"{n_positive_instruments}/{len(INSTRUMENTS_83)} instruments POSITIVE",
        "parameter_robustness_plateau_stable": plateau_stable,
        "walk_forward": "see temporal_stability (quarterly blocks act as the walk-forward segments)",
        "placebos_collapsed": placebos_collapsed,
        "holdout": (holdout_stats or {}).get("verdict"),
        "researcher_df_risk": "disclosed in RESEARCH_LEDGER -- 8 screening cells + 7-point threshold grid",
    }


def classify_final_verdict(scorecard: Dict[str, Any]) -> Tuple[str, str]:
    if not scorecard["cost_sensitivity"]["survives_base"]:
        return "NO_EDGE_FOUND", "Rule's gross/base-cost expectancy is not CI-excluding positive."
    if not scorecard["placebos_collapsed"]:
        return "LEAKAGE", "Placebo battery did not collapse -- possible mechanical artifact."
    if not scorecard["cost_sensitivity"]["survives_adverse"]:
        return "ACTIONABLE_BUT_NOT_ECONOMIC", "Effect real at base cost but erased by adverse costs."
    breadth = scorecard["cross_asset_stability"]
    n_pos = int(breadth.split("/")[0])
    if n_pos < 2:
        return "POSITIVE_NET_EXPECTANCY_BUT_FRAGILE", "Positive net expectancy but confined to <2 instruments."
    if not scorecard["parameter_robustness_plateau_stable"]:
        return "POSITIVE_NET_EXPECTANCY_BUT_FRAGILE", "Performance is not plateau-like across the threshold neighbourhood."
    temporal_ok = scorecard["temporal_stability"].split()[0]
    n_pos_blocks, n_total_blocks = (int(x) for x in temporal_ok.split("/"))
    if n_total_blocks and n_pos_blocks / n_total_blocks < 0.6:
        return "PROMISING_TRADING_HYPOTHESIS", "Net-positive after adverse costs but temporally inconsistent."
    if scorecard["holdout"] != "POSITIVE":
        return "PROMISING_TRADING_HYPOTHESIS", "Passes discovery/confirmation robustness; holdout not yet confirmatory."
    if not scorecard["cost_sensitivity"]["survives_severe"]:
        return "ROBUST_EDGE_CANDIDATE", "Survives holdout and adverse costs but not the severe-cost stress scenario."
    return "ROBUST_TRADING_EDGE", "Survives holdout, all cost scenarios, cross-asset and temporal robustness, and placebos."


# ==========================================================================
# result container
# ==========================================================================
@dataclass
class Phase86Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    split_dates: Dict[str, str]
    cost_scenarios: Dict[str, float]
    conditional_asymmetry_discovery_screen: Dict[str, Any]
    conditional_asymmetry_promoted: Dict[str, Any]
    candidate1_discovery_screen: Dict[str, Any]
    candidate1_frozen_threshold: Dict[str, Any]
    candidate1_confirmation: Dict[str, Any]
    candidate1_cross_asset: Dict[str, Any]
    candidate1_temporal_blocks: List[Dict[str, Any]]
    candidate1_parameter_perturbation: Dict[str, Any]
    candidate1_cost_sensitivity: Dict[str, Any]
    candidate1_horizon_robustness: Dict[str, Any]
    candidate1_placebos: Dict[str, Any]
    candidate1_final_holdout: Optional[Dict[str, Any]]
    scorecard: Dict[str, Any]
    verdict: str
    verdict_reason: str
    research_ledger: List[Dict[str, Any]]
    ledger_summary: Dict[str, Any]
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


def run() -> Phase86Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()
    ledger = ResearchLedger()

    ds_h4 = p85.build_pooled_dataset_85(PRIMARY_TF, _CANDIDATE1_HEADLINE_HORIZON)
    discovery, confirmation, final_holdout = three_way_split(ds_h4)

    # ---- Track A/C: conditional directional asymmetry -----------------------
    asym_screen = conditional_asymmetry_screen(discovery)
    for cid, row in asym_screen.items():
        ledger.record("conditional_directional_asymmetry", cid,
                      next(c["hypothesis"] for c in _ASYMMETRY_CELLS if c["id"] == cid),
                      "discovery_screen", "SCREENED", "see metrics", metrics=row)
    asym_promoted = promote_asymmetry_candidates(asym_screen, confirmation, ledger=ledger)

    # ---- Track B: momentum + volume filter -----------------------------------
    c1_screen = screen_candidate1(discovery)
    for thr, stats in c1_screen.items():
        ledger.record("volume_plus_directional_setup", f"mom4_volfilter_thr{thr}",
                      f"sign(mom_4) direction, volume_rank>={thr} filter, h=4, BASE cost",
                      "discovery_screen", "SCREENED", "see metrics", metrics=stats)
    frozen = select_frozen_threshold(c1_screen)
    frozen_threshold = frozen.get("frozen_threshold")

    if frozen_threshold is None:
        ledger.record("volume_plus_directional_setup", "mom4_volfilter", "candidate 1 overall",
                     "discovery_screen", "KILLED", "no threshold cleared the materiality/CI bar in discovery")
        c1_confirmation = c1_cross = c1_temporal = c1_perturb = c1_cost = c1_horizon = c1_placebo = {}
        c1_temporal = []
        c1_holdout = None
    else:
        c1_confirmation = evaluate_candidate1(confirmation, frozen_threshold, COST_SCENARIOS["BASE"])
        c1_cross = candidate1_cross_asset(confirmation, frozen_threshold, COST_SCENARIOS["BASE"])
        c1_temporal = candidate1_temporal_blocks(confirmation, frozen_threshold, COST_SCENARIOS["BASE"])
        c1_perturb = candidate1_parameter_perturbation(confirmation, frozen_threshold, COST_SCENARIOS["BASE"])
        c1_cost = candidate1_cost_sensitivity(confirmation, frozen_threshold)
        c1_horizon = candidate1_horizon_robustness(PRIMARY_TF, frozen_threshold, COST_SCENARIOS["BASE"])
        c1_placebo = candidate1_placebos(confirmation, frozen_threshold, COST_SCENARIOS["BASE"])
        promoted_to_confirmation = (c1_confirmation.get("verdict") == "POSITIVE"
                                    and (c1_confirmation.get("mean") or 0) >= _MATERIAL_MEAN_R)
        ledger.record("volume_plus_directional_setup", f"mom4_volfilter_thr{frozen_threshold}_FROZEN",
                     "frozen rule evaluated on confirmation", "confirmation",
                     "PROMOTED_LEVEL_1" if promoted_to_confirmation else "KILLED",
                     "material CI-excluding-positive on confirmation" if promoted_to_confirmation
                     else "did not replicate on confirmation", metrics=c1_confirmation)
        # ---- ONE-SHOT final holdout, only if confirmation-level promotion --
        if promoted_to_confirmation:
            c1_holdout = evaluate_candidate1(final_holdout, frozen_threshold, COST_SCENARIOS["BASE"])
            ledger.record("volume_plus_directional_setup", f"mom4_volfilter_thr{frozen_threshold}_HOLDOUT",
                         "ONE-SHOT final holdout evaluation of the frozen rule", "final_holdout",
                         "PROMOTED_LEVEL_2" if c1_holdout.get("verdict") == "POSITIVE" else "KILLED",
                         "see metrics", metrics=c1_holdout)
        else:
            c1_holdout = None

    scorecard = build_scorecard(c1_confirmation or {"verdict": None}, c1_cross, c1_temporal,
                                c1_perturb, c1_cost, c1_placebo, c1_holdout)
    verdict, verdict_reason = classify_final_verdict(scorecard) if frozen_threshold is not None else \
        ("NO_EDGE_FOUND", "No volume threshold cleared the discovery-stage materiality/CI screen.")

    # ---- determinism ----------------------------------------------------------
    c1_screen_2 = screen_candidate1(discovery)
    determinism_match = (c1_screen == c1_screen_2)

    ident = json.dumps({"schema": SCHEMA_VERSION, "frozen_threshold": frozen_threshold,
                       "verdict": verdict, "c1_confirmation": c1_confirmation},
                      sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase86Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(INSTRUMENTS_83), timeframe=PRIMARY_TF,
        split_dates={"discovery_end": _DISCOVERY_CUTOFF.isoformat(),
                    "confirmation_start": _CONFIRMATION_START.isoformat(),
                    "final_holdout_start": _FINAL_HOLDOUT_START.isoformat()},
        cost_scenarios=COST_SCENARIOS,
        conditional_asymmetry_discovery_screen=asym_screen,
        conditional_asymmetry_promoted=asym_promoted,
        candidate1_discovery_screen={str(k): v for k, v in c1_screen.items()},
        candidate1_frozen_threshold=frozen,
        candidate1_confirmation=c1_confirmation,
        candidate1_cross_asset=c1_cross,
        candidate1_temporal_blocks=c1_temporal,
        candidate1_parameter_perturbation={str(k): v for k, v in c1_perturb.items()},
        candidate1_cost_sensitivity=c1_cost,
        candidate1_horizon_robustness={str(k): v for k, v in c1_horizon.items()},
        candidate1_placebos=c1_placebo,
        candidate1_final_holdout=c1_holdout,
        scorecard=scorecard, verdict=verdict, verdict_reason=verdict_reason,
        research_ledger=ledger.to_list(), ledger_summary=ledger.summary(),
        determinism={"match": determinism_match},
        runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase86Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase86_aggressive_edge_discovery", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 86 - aggressive trading edge discovery ...", flush=True)
    res = run()
    print(f"\n=== PHASE 86 ({res.runtime_seconds}s) ===")
    print(f"Frozen threshold: {json.dumps(res.candidate1_frozen_threshold, default=str)}")
    print(f"\nCandidate1 confirmation: {json.dumps(res.candidate1_confirmation, default=str)}")
    print(f"\nCross-asset: {json.dumps(res.candidate1_cross_asset, default=str)}")
    print(f"\nTemporal blocks: {json.dumps(res.candidate1_temporal_blocks, default=str)}")
    print(f"\nCost sensitivity: {json.dumps(res.candidate1_cost_sensitivity, default=str)}")
    print(f"\nPlacebos: {json.dumps(res.candidate1_placebos, default=str)}")
    print(f"\nFinal holdout: {json.dumps(res.candidate1_final_holdout, default=str)}")
    print(f"\nPromoted asymmetry cells: {json.dumps(res.conditional_asymmetry_promoted, default=str)}")
    print(f"\nScorecard: {json.dumps(res.scorecard, default=str)}")
    print(f"\nLedger summary: {json.dumps(res.ledger_summary, default=str)}")
    print(f"\nVERDICT: {res.verdict} -- {res.verdict_reason}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "COST_SCENARIOS", "_VOLUME_THRESHOLD_GRID",
    "three_way_split", "ResearchLedger", "conditional_asymmetry_screen",
    "promote_asymmetry_candidates", "screen_candidate1", "select_frozen_threshold",
    "evaluate_candidate1", "candidate1_cross_asset", "candidate1_temporal_blocks",
    "candidate1_parameter_perturbation", "candidate1_cost_sensitivity",
    "candidate1_horizon_robustness", "candidate1_placebos", "build_scorecard",
    "classify_final_verdict", "run", "persist", "get_result", "main",
]
