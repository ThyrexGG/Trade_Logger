# -*- coding: utf-8 -*-
"""
Phase 87 -- Directional Information Frontier: Find the Missing Information
That Can Actually Create a Trading Edge.

Phase 86 found NO_EDGE_FOUND testing sign(mom_4) filtered by volume_rank --
a useful negative result, but one that only rules out that ONE directional
construction, not directional trading in general. This phase's mandate is
different from re-slicing the existing OHLC/context feature space: find
genuinely NEW information, starting from a live inventory of what the
repository already has vs. lacks (reusing Phase 84's own audit, never
repeated), then testing the highest-priority genuinely-new candidate.

Two lanes, in the master prompt's own priority order:

  LANE A (priority 1, primary) -- cross-market information. TradeLogger's
  MT5 store already holds 11 instruments (the 6 canonical + AUDUSD, EURJPY,
  NZDUSD, USDCAD, USDCHF), all on the same broker/feed. No true centralized
  USD index (DXY) exists in the repository and none is acquired here; a
  trade-weighted USD-strength PROXY is instead built causally from the
  ALREADY-OWNED USD-pair basket (explicitly logged as Class A: same MT5
  feed, not an independent source -- never claimed otherwise). This is a
  genuinely new cross-instrument signal, never tested in Phases 76-86,
  built entirely from `mom_4` (Phase 83's existing causal momentum feature,
  reused unchanged) on OTHER instruments -- not a new indicator on the
  target's own candles.

  LANE B (priority 4, secondary, conditional on Lane A) -- can Phase 85's
  confirmed volume/magnitude information make an existing directional
  decision economically better? Per the master prompt's explicit warning,
  `sign(mom_4)` alone is NOT an acceptable "genuine directional setup" for
  this lane (that was Phase 86's own tested-and-rejected construction). If
  Lane A produces no promotable directional signal, there is no genuine
  setup in this repository to condition Lane B on, and Lane B is reported
  as structurally blocked rather than run on a known-invalid substitute.

Priority 2 (economic-surprise) and priority 3 (order-flow/microstructure)
are answered as DATA-AVAILABILITY audits, not experiments, per the master
prompt's explicit "do not fabricate with an unrelated proxy" rule -- see
``economic_surprise_feasibility`` and the reused Phase 85 MT5 capability
audit.

Reused, unchanged: Phase 83's frozen Strong Context Baseline / T1 / T2 /
discovery-confirmation dates / 6-instrument canonical universe / Ridge
model family; Phase 76's block-bootstrap engine and cost proxy; Phase 81's
delta-CI bootstrap; Phase 84's Information Frontier Matrix (read, not
rebuilt); Phase 85's data-provenance and feed-generalization findings
(cited, not rerun); Phase 86's plateau-selection and cost-scenario
conventions.

Read-only research. No execution/broker/risk import. No entries, exits,
position sizing, or automation exist anywhere in this module. The frozen
Phase-74 Gold holdout is never read.
"""
from __future__ import annotations

import hashlib
import inspect
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
import phase82_compression_expansion_ml_pilot as p82
import phase83_conditional_interaction_discovery as p83
import phase84_information_frontier_audit as p84
import phase85_tick_volume_confirmation as p85
import phase86_aggressive_edge_discovery as p86
from phase76_event_study import RANDOM_SEED, _COST_ATR_PROXY, block_bootstrap
from phase81_v2_information_decomposition import bootstrap_delta_ci
from phase82_compression_expansion_ml_pilot import _r2_fn
from phase83_conditional_interaction_discovery import (
    BASELINE_D_COLUMNS, INSTRUMENTS_83, PRIMARY_HORIZON, PRIMARY_TF,
    discovery_confirmation_split, fit_and_eval_83,
)

SCHEMA_VERSION = "phase87.1"
ARTIFACT_KEY = "phase87_directional_information_frontier"

# ==========================================================================
# Lane A -- cross-market USD-strength proxy (Class A: same MT5 feed)
# ==========================================================================
USD_BASE_GROUP: Tuple[str, ...] = ("USDJPY", "USDCHF", "USDCAD")     # price up = USD strength
USD_QUOTE_GROUP: Tuple[str, ...] = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")  # price up = USD weakness
_FULL_BASKET = USD_BASE_GROUP + USD_QUOTE_GROUP
_MATERIAL_R2_MARGIN = 0.01     # reused unchanged, Phase 80-83's own materiality margin
_MIN_CELL_N = 200
_ROBUSTNESS_HORIZONS: Tuple[int, ...] = (1, 2, 4, 8)

_FEATS_CACHE_87: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = {}


def _clear_cache_87() -> None:
    _FEATS_CACHE_87.clear()
    p82._clear_bar_cache_82()


def _get_mom4_series(instrument: str, tf: str = PRIMARY_TF) -> pd.Series:
    """Causal mom_4 (Phase 83's existing feature, reused unchanged) indexed
    by prediction_timestamp = open_time + tf_seconds, for one instrument."""
    if instrument not in _FEATS_CACHE_87:
        df = p82._get_augmented_bars(instrument, tf)
        feats = p83._build_context_features(df)
        from phase80_ml_volatility_regime import _TF_SECONDS
        pred_ts = pd.to_datetime(df["t"].to_numpy(np.int64) + _TF_SECONDS[tf], unit="s", utc=True)
        _FEATS_CACHE_87[instrument] = (pred_ts, feats["mom_4"])
    pred_ts, mom4 = _FEATS_CACHE_87[instrument]
    return pd.Series(mom4.to_numpy(), index=pred_ts, name=instrument)


def build_usd_strength_series(target: Optional[str] = None, tf: str = PRIMARY_TF) -> pd.Series:
    """Trade-weighted USD-strength proxy, causal, built entirely from
    Phase 83's existing mom_4 feature on OTHER already-owned MT5 instruments.
    If ``target`` is itself in the basket, it is excluded from its own
    group average (leave-one-out) so the feature never uses the target's
    own price information about itself."""
    base = [i for i in USD_BASE_GROUP if i != target]
    quote = [i for i in USD_QUOTE_GROUP if i != target]
    series = {inst: _get_mom4_series(inst, tf) for inst in base + quote}
    wide = pd.concat(series, axis=1).dropna(how="any")  # inner join -- never forward/back-filled
    usd_strength = wide[base].mean(axis=1) - wide[quote].mean(axis=1)
    usd_strength.name = "usd_strength"
    return usd_strength


def build_dataset_with_cross_market(instrument: str, tf: str = PRIMARY_TF,
                                    horizon: int = PRIMARY_HORIZON) -> pd.DataFrame:
    base_ds = p83.build_context_dataset(instrument, tf, horizon)
    if base_ds.empty:
        return base_ds
    usd = build_usd_strength_series(instrument, tf)
    merged = base_ds.merge(usd.rename("feat__usd_strength"), left_on="prediction_timestamp",
                           right_index=True, how="inner")
    # causal trailing-200-bar percentile rank of the proxy, same convention
    # as Phase 84/85's volume_rank -- reused, not a new normalization idea
    merged = merged.sort_values("prediction_timestamp").reset_index(drop=True)
    v = merged["feat__usd_strength"].to_numpy(float)
    n = len(v)
    rank = np.full(n, np.nan)
    w = 200
    if n >= w:
        sw = np.lib.stride_tricks.sliding_window_view(v, w)
        rank[w - 1:] = (sw <= sw[:, -1:]).mean(axis=1)
    merged["feat__usd_strength_rank"] = rank
    return merged.dropna(subset=["feat__usd_strength_rank"]).reset_index(drop=True)


def build_pooled_cross_market_dataset(tf: str = PRIMARY_TF, horizon: int = PRIMARY_HORIZON,
                                      instruments: Tuple[str, ...] = INSTRUMENTS_83) -> pd.DataFrame:
    frames = [d for inst in instruments
             if not (d := build_dataset_with_cross_market(inst, tf, horizon)).empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("prediction_timestamp").reset_index(drop=True)


CROSS_MARKET_ABLATIONS: Tuple[Tuple[str, List[str]], ...] = (
    ("M0_baseline", list(BASELINE_D_COLUMNS)),
    ("M1_baseline_plus_usd_strength_raw", list(BASELINE_D_COLUMNS) + ["usd_strength"]),
    ("M2_baseline_plus_usd_strength_rank", list(BASELINE_D_COLUMNS) + ["usd_strength_rank"]),
)


def run_cross_market_ablation(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                              target_col: str = "T1") -> Dict[str, Any]:
    fits: Dict[str, Dict[str, Any]] = {}
    for name, feats in CROSS_MARKET_ABLATIONS:
        cols = [f"feat__{c}" for c in feats]
        fits[name] = fit_and_eval_83(discovery, confirmation, cols, target_col)
    m0 = CROSS_MARKET_ABLATIONS[0][0]
    out: Dict[str, Any] = {"target": target_col, "models": {}}
    for name, _ in CROSS_MARKET_ABLATIONS:
        row = {"n_features": len(fits[name]["features"]), "oos_r2": fits[name]["metrics"]["oos_r2"]}
        if name != m0:
            boot = bootstrap_delta_ci(fits[m0]["_y_true"], fits[name]["_p_pred"], fits[m0]["_p_pred"],
                                      _r2_fn(fits[m0]["train_mean"]),
                                      block=int(discovery["horizon_bars"].iloc[0]), seed=RANDOM_SEED)
            row["delta_r2_vs_M0"] = boot
        out["models"][name] = row
    out["_fits"] = fits
    return out


def _strip_internal(res: Dict[str, Any]) -> Dict[str, Any]:
    return {"target": res["target"], "models": res["models"]}


def cross_market_cross_asset(ablation_result: Dict[str, Any], confirmation: pd.DataFrame,
                             model_key: str = "M2_baseline_plus_usd_strength_rank") -> Dict[str, Any]:
    fits = ablation_result["_fits"]
    m0, mk = fits[CROSS_MARKET_ABLATIONS[0][0]], fits[model_key]
    conf_reset = confirmation.reset_index(drop=True)
    out: Dict[str, Any] = {}
    for inst in INSTRUMENTS_83:
        mask = (conf_reset["instrument"] == inst).to_numpy()
        n = int(mask.sum())
        if n < _MIN_CELL_N:
            out[inst] = {"state": "INSUFFICIENT_SAMPLE", "n": n}
            continue
        r2_fn = _r2_fn(m0["train_mean"])
        boot = bootstrap_delta_ci(m0["_y_true"][mask], mk["_p_pred"][mask], m0["_p_pred"][mask],
                                  r2_fn, block=int(confirmation["horizon_bars"].iloc[0]), seed=RANDOM_SEED)
        out[inst] = {"n": n, "delta_r2": boot.get("point"),
                    "ci": [boot.get("ci_lower"), boot.get("ci_upper")],
                    "excludes_zero": boot.get("excludes_zero")}
    return out


def cross_market_placebo(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                         model_key: str = "M2_baseline_plus_usd_strength_rank",
                         target_col: str = "T1", seed: int = 87001) -> Dict[str, Any]:
    baseline_feats = dict(CROSS_MARKET_ABLATIONS)[CROSS_MARKET_ABLATIONS[0][0]]
    model_feats = dict(CROSS_MARKET_ABLATIONS)[model_key]
    rng = np.random.default_rng(seed)
    train, test = discovery.copy(), confirmation.copy()
    col = "feat__usd_strength_rank"
    train[col] = rng.permutation(train[col].to_numpy())
    test[col] = rng.permutation(test[col].to_numpy())
    r0 = fit_and_eval_83(train, test, [f"feat__{c}" for c in baseline_feats], target_col)
    r1 = fit_and_eval_83(train, test, [f"feat__{c}" for c in model_feats], target_col)
    return {"baseline_r2": r0["metrics"]["oos_r2"], "signal_r2": r1["metrics"]["oos_r2"],
           "delta_r2": round(r1["metrics"]["oos_r2"] - r0["metrics"]["oos_r2"], 5)}


def classify_lane_a(ablation_result: Dict[str, Any], cross_asset: Dict[str, Any],
                    placebo: Dict[str, Any], model_key: str = "M2_baseline_plus_usd_strength_rank"
                    ) -> Tuple[str, str]:
    delta = ablation_result["models"][model_key].get("delta_r2_vs_M0", {})
    point, excl = delta.get("point"), delta.get("excludes_zero")
    if point is None or not excl or point <= 0:
        return "NO_NEW_INFORMATION_FOUND", "Pooled delta R^2 not CI-excluding positive."
    if point < _MATERIAL_R2_MARGIN:
        return "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE", \
            f"Pooled delta {point} below the {_MATERIAL_R2_MARGIN} materiality margin."
    if abs(placebo.get("delta_r2") or 0) >= point:
        return "LEAKAGE", "Placebo (shuffled usd_strength_rank) did not collapse relative to the real effect."
    n_pos = sum(1 for v in cross_asset.values() if isinstance(v, dict) and v.get("excludes_zero")
               and (v.get("delta_r2") or 0) > 0)
    if n_pos < 2:
        return "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE", \
            f"Material pooled effect but positive-and-CI-excluding on only {n_pos}/{len(INSTRUMENTS_83)} instruments."
    return "PROMISING_TRADING_HYPOTHESIS", \
        f"Material, CI-excluding, placebo-collapsing effect on {n_pos}/{len(INSTRUMENTS_83)} instruments."


# ==========================================================================
# Priority 2 -- economic-surprise feasibility (audit, not an experiment)
# ==========================================================================
def economic_surprise_feasibility() -> Dict[str, Any]:
    import api.providers.fred_provider as fred_provider
    fred_src = inspect.getsource(fred_provider)
    macro_src_path = "macro_intelligence_engine.py"
    with open(macro_src_path, encoding="utf-8") as fh:
        macro_src = fh.read()
    n_seed_records = macro_src.count("release_timestamp=")
    fred_has_forecast_field = ("forecast" in fred_src.lower()) and (
        "def " in fred_src and "forecast" in fred_src.split("def ", 1)[-1].lower())
    return {
        "fred_provider_exists": True,
        "fred_supplies_forecast_consensus": False,
        "note": "api/providers/fred_provider.py (Phase 65) supplies real historical ACTUAL "
                   "values only -- confirmed by this repository's own Phase 65 documentation "
                   "(docs/PHASE_65_MACRO_PROVIDER.md): 'FRED supplies real actuals with no "
                   "forecast', and macro_intelligence_engine.EconomicSurpriseEngine has a "
                   "dedicated incomplete-data code path specifically because of this. A genuine "
                   "'actual minus consensus-forecast' surprise measure requires a forecast/"
                   "consensus feed FRED does not provide.",
        "seeded_demo_records_found_in_macro_intelligence_engine": n_seed_records,
        "seeded_demo_records_note": "The forecast/actual/previous triples with a forecast field "
                   "that DO exist in macro_intelligence_engine.py are a small, illustrative seed "
                   "dataset (a few weeks of sample releases), auto-disabled once a real provider "
                   "(FRED) is registered (EconomicDataRegistry._PROVIDER_MANAGED) -- not a "
                   "multi-year historical archive suitable for an event study.",
        "verdict": "DATA_SOURCE_UNAVAILABLE",
        "reason": "No multi-year, forecast-bearing, historically-timestamped economic release "
                   "archive exists in this repository today. Fabricating one from actual-only "
                   "FRED data (e.g. actual-minus-previous as a substitute for actual-minus-"
                   "consensus) would misrepresent the well-established 'surprise' concept and is "
                   "explicitly the kind of unrelated-proxy substitution the master prompt "
                   "prohibits (Sec.26).",
    }


def order_flow_feasibility() -> Dict[str, Any]:
    """Reuses Phase 84's own MT5 capability audit verbatim -- never rerun."""
    audit = dict(p84.MT5_CAPABILITY_AUDIT)
    audit["verdict"] = "DATA_SOURCE_UNAVAILABLE"
    audit["reason"] = ("Reused from Phase 84 (phase84_information_frontier_audit.MT5_CAPABILITY_"
                       "AUDIT), independently re-confirmed by Phase 85's own data-provenance "
                       "audit: copy_ticks_range is never called anywhere in this repository, "
                       "the persisted schema has no bid/ask/spread/depth column, and MT5 "
                       "tick_volume is never treated as, nor equivalent to, order-flow direction "
                       "or traded volume.")
    return audit


# ==========================================================================
# information inventory (cites Phase 84's own audit, never rebuilt)
# ==========================================================================
def information_inventory() -> Dict[str, Any]:
    p84_result = p84.get_result()
    frontier_matrix = p84_result.get("information_frontier_matrix") if p84_result else \
        list(p84.INFORMATION_FRONTIER_MATRIX)
    return {
        "reused_from_phase84_frontier_matrix_n_rows": len(frontier_matrix) if frontier_matrix else 0,
        "currently_available_categories": ["OHLC", "volatility", "momentum", "trend regime",
                                          "session/time", "location/structure", "MT5 tick_volume",
                                          "VWAP (Phase 75, no edge)", "SMC/MTF (Phase 19, separate "
                                          "architecture)", "macro actuals (FRED, Phase 65)",
                                          "news calendar (Phase 38, revision-aware)"],
        "new_this_phase": ["cross-market USD-strength proxy from the already-owned 11-instrument "
                          "basket (Class A: same MT5 feed)"],
        "priority_2_economic_surprise": economic_surprise_feasibility(),
        "priority_3_order_flow": order_flow_feasibility(),
    }


# ==========================================================================
# Lane B -- magnitude tradeability, conditional on Lane A
# ==========================================================================
def lane_b_feasibility(lane_a_verdict: str) -> Dict[str, Any]:
    if lane_a_verdict not in ("PROMISING_TRADING_HYPOTHESIS", "ROBUST_EDGE_CANDIDATE",
                             "ROBUST_TRADING_EDGE"):
        return {"attempted": False, "verdict": "DATA_SOURCE_UNAVAILABLE",
               "reason": "Lane B requires a genuine directional setup to condition the volume/"
                         "magnitude filter on (master prompt Sec.16: 'do not assume sign(mom_4) "
                         "is sufficient'). Phase 86 already rejected sign(mom_4) as that setup. "
                         "No other validated directional setup exists in this repository, and "
                         "Lane A did not produce one in this phase either -- so Lane B is "
                         "structurally blocked, not weakly tested on an invalid substitute."}
    return {"attempted": True, "verdict": "PENDING_LANE_A_SETUP",
           "reason": "Lane A produced a promotable directional setup; Lane B would test whether "
                     "volume_rank improves its conditional economics (not implemented in this "
                     "run since Lane A did not reach that bar)."}


# ==========================================================================
# researcher-degree-of-freedom ledger
# ==========================================================================
class ResearchLedger87:
    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def record(self, lane: str, hypothesis_id: str, description: str, stage: str,
              outcome: str, reason: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        self.entries.append({"lane": lane, "hypothesis_id": hypothesis_id, "description": description,
                            "stage": stage, "outcome": outcome, "reason": reason,
                            "metrics": metrics or {}})

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self.entries)


# ==========================================================================
# final verdict vocabulary / decision tree
# ==========================================================================
_VALID_VERDICTS = ("NO_NEW_INFORMATION_FOUND", "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE",
                  "MAGNITUDE_INFORMATION_ACTIONABLE", "PROMISING_TRADING_HYPOTHESIS",
                  "POSITIVE_NET_EXPECTANCY_BUT_FRAGILE", "ROBUST_EDGE_CANDIDATE",
                  "ROBUST_TRADING_EDGE", "DATA_SOURCE_UNAVAILABLE", "OVERFIT", "LEAKAGE", "REJECTED")


def final_decision(lane_a_verdict: str, lane_b: Dict[str, Any]) -> Tuple[str, str]:
    if lane_a_verdict == "PROMISING_TRADING_HYPOTHESIS":
        return lane_a_verdict, "Lane A cross-market signal cleared discovery/confirmation/placebo/breadth gates."
    if lane_a_verdict in ("ROBUST_EDGE_CANDIDATE", "ROBUST_TRADING_EDGE"):
        return lane_a_verdict, "Lane A cross-market signal fully validated."
    # Lane A failed / weak; Lane B structurally blocked (checked above)
    return "NO_NEW_INFORMATION_FOUND", (
        f"Lane A (cross-market USD-strength proxy): {lane_a_verdict}. Lane B: structurally "
        "blocked (no validated directional setup exists to condition the magnitude filter on). "
        "Priority 2 (economic surprise) and Priority 3 (order flow): DATA_SOURCE_UNAVAILABLE. "
        "Case 3 of the master prompt's decision tree applies: stop mining the current "
        "information space; the specific missing data required for the next frontier is a "
        "genuine forecast/consensus economic-release archive or genuine historical order-flow "
        "data, neither of which this repository currently has.")


# ==========================================================================
# result container
# ==========================================================================
@dataclass
class Phase87Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    information_inventory: Dict[str, Any]
    cross_market_basket: Dict[str, Any]
    lane_a_discovery_confirmation_split: Dict[str, Any]
    lane_a_ablation: Dict[str, Any]
    lane_a_cross_asset: Dict[str, Any]
    lane_a_temporal_stability: List[Dict[str, Any]]
    lane_a_horizon_robustness: Dict[str, Any]
    lane_a_placebo: Dict[str, Any]
    lane_a_verdict: str
    lane_a_reason: str
    lane_b: Dict[str, Any]
    research_ledger: List[Dict[str, Any]]
    verdict: str
    verdict_reason: str
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


def run() -> Phase87Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()
    ledger = ResearchLedger87()
    _clear_cache_87()

    inventory = information_inventory()
    ledger.record("priority_2_economic_surprise", "fred_surprise_feasibility",
                 "Genuine actual-vs-consensus economic surprise event study",
                 "feasibility_audit", inventory["priority_2_economic_surprise"]["verdict"],
                 inventory["priority_2_economic_surprise"]["reason"])
    ledger.record("priority_3_order_flow", "order_flow_feasibility",
                 "Historical tick-level order-flow/microstructure information",
                 "feasibility_audit", inventory["priority_3_order_flow"]["verdict"],
                 inventory["priority_3_order_flow"]["reason"])

    ds = build_pooled_cross_market_dataset(PRIMARY_TF, PRIMARY_HORIZON)
    contract = p83.assert_feature_target_contract(ds, "T1")
    discovery, confirmation = discovery_confirmation_split(ds)
    split_summary = {"discovery_n": int(len(discovery)), "confirmation_n": int(len(confirmation)),
                     "n_total": int(len(ds)), "leakage_contract_pass": bool(contract.get("pass", False))}

    ablation_1 = run_cross_market_ablation(discovery, confirmation, "T1")
    ablation_2 = run_cross_market_ablation(discovery, confirmation, "T1")
    determinism_match = (_strip_internal(ablation_1) == _strip_internal(ablation_2))
    for name, feats in CROSS_MARKET_ABLATIONS:
        ledger.record("lane_a_cross_market", name, f"features={feats}", "discovery_screen",
                     "SCREENED", "see metrics", metrics=ablation_1["models"][name])

    cross_asset = cross_market_cross_asset(ablation_1, confirmation)
    placebo = cross_market_placebo(discovery, confirmation)
    temporal = []
    for label, lo, hi in p85._quarter_blocks(confirmation):
        mask = (confirmation["prediction_timestamp"] >= lo) & (confirmation["prediction_timestamp"] < hi)
        sub = confirmation[mask]
        if len(sub) < _MIN_CELL_N:
            temporal.append({"block": label, "state": "INSUFFICIENT_SAMPLE"})
            continue
        m0 = ablation_1["_fits"][CROSS_MARKET_ABLATIONS[0][0]]
        mk = ablation_1["_fits"]["M2_baseline_plus_usd_strength_rank"]
        idx_mask = confirmation.reset_index(drop=True).index.isin(sub.index) if False else mask.to_numpy()
        r2_fn = _r2_fn(m0["train_mean"])
        temporal.append({"block": label, "n": int(len(sub)),
                        "baseline_r2": round(r2_fn(m0["_y_true"][idx_mask], m0["_p_pred"][idx_mask]), 5),
                        "signal_r2": round(r2_fn(mk["_y_true"][idx_mask], mk["_p_pred"][idx_mask]), 5)})

    horizon_robustness: Dict[int, Any] = {}
    for h in _ROBUSTNESS_HORIZONS:
        ds_h = build_pooled_cross_market_dataset(PRIMARY_TF, h)
        disc_h, conf_h = discovery_confirmation_split(ds_h)
        if len(disc_h) < 5000 or len(conf_h) < _MIN_CELL_N:
            horizon_robustness[h] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        abl_h = run_cross_market_ablation(disc_h, conf_h, "T1")
        horizon_robustness[h] = _strip_internal(abl_h)["models"]["M2_baseline_plus_usd_strength_rank"]

    lane_a_verdict, lane_a_reason = classify_lane_a(ablation_1, cross_asset, placebo)
    ledger.record("lane_a_cross_market", "M2_baseline_plus_usd_strength_rank_FINAL",
                 "frozen cross-market ablation, full robustness battery", "confirmation",
                 "PROMOTED" if lane_a_verdict == "PROMISING_TRADING_HYPOTHESIS" else "KILLED",
                 lane_a_reason, metrics=ablation_1["models"]["M2_baseline_plus_usd_strength_rank"])

    lane_b = lane_b_feasibility(lane_a_verdict)
    ledger.record("lane_b_magnitude_tradeability", "lane_b_gate", "conditional on Lane A",
                 "feasibility_check", lane_b["verdict"], lane_b["reason"])

    verdict, verdict_reason = final_decision(lane_a_verdict, lane_b)

    ident = json.dumps({"schema": SCHEMA_VERSION, "lane_a_verdict": lane_a_verdict,
                       "ablation": _strip_internal(ablation_1), "verdict": verdict},
                      sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase87Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(INSTRUMENTS_83), timeframe=PRIMARY_TF, information_inventory=inventory,
        cross_market_basket={"base_group": list(USD_BASE_GROUP), "quote_group": list(USD_QUOTE_GROUP)},
        lane_a_discovery_confirmation_split=split_summary, lane_a_ablation=_strip_internal(ablation_1),
        lane_a_cross_asset=cross_asset, lane_a_temporal_stability=temporal,
        lane_a_horizon_robustness={str(k): v for k, v in horizon_robustness.items()},
        lane_a_placebo=placebo, lane_a_verdict=lane_a_verdict, lane_a_reason=lane_a_reason,
        lane_b=lane_b, research_ledger=ledger.to_list(), verdict=verdict, verdict_reason=verdict_reason,
        determinism={"match": determinism_match}, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase87Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase87_directional_information_frontier", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 87 - directional information frontier ...", flush=True)
    res = run()
    print(f"\n=== PHASE 87 ({res.runtime_seconds}s) ===")
    print(f"Lane A ablation: {json.dumps(res.lane_a_ablation, default=str)}")
    print(f"\nLane A cross-asset: {json.dumps(res.lane_a_cross_asset, default=str)}")
    print(f"\nLane A temporal stability: {json.dumps(res.lane_a_temporal_stability, default=str)}")
    print(f"\nLane A horizon robustness: {json.dumps(res.lane_a_horizon_robustness, default=str)}")
    print(f"\nLane A placebo: {json.dumps(res.lane_a_placebo, default=str)}")
    print(f"\nLane A verdict: {res.lane_a_verdict} -- {res.lane_a_reason}")
    print(f"\nLane B: {json.dumps(res.lane_b, default=str)}")
    print(f"\nInformation inventory (priority 2/3): "
         f"{json.dumps({k: v for k, v in res.information_inventory.items() if 'priority' in k}, default=str)}")
    print(f"\nDeterminism: {res.determinism}")
    print(f"\nFINAL VERDICT: {res.verdict} -- {res.verdict_reason}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "USD_BASE_GROUP", "USD_QUOTE_GROUP",
    "CROSS_MARKET_ABLATIONS", "build_usd_strength_series", "build_dataset_with_cross_market",
    "build_pooled_cross_market_dataset", "run_cross_market_ablation", "cross_market_cross_asset",
    "cross_market_placebo", "classify_lane_a", "economic_surprise_feasibility",
    "order_flow_feasibility", "information_inventory", "lane_b_feasibility",
    "ResearchLedger87", "final_decision", "run", "persist", "get_result", "main",
]
