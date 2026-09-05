# -*- coding: utf-8 -*-
"""
Phase 88 -- External Information Acquisition & Aggressive Directional Edge
Hunt.

Phase 87 established that cross-market information built from already-
owned MT5 instruments (same feed) adds essentially zero directional
information. This phase's mandate is different: acquire genuinely NEW,
independent information and determine whether it creates an actionable
directional edge.

Tier audit (master prompt Sec.4-6), performed by direct inspection, never
assumed:
  * Tier 1 (economic surprise: actual/forecast/previous with real
    historical depth) -- verified UNAVAILABLE.
    `xauusd_daily_preflight.ForexFactoryProvider.get_calendar` contains no
    network call at all (grep for `requests`/`http` inside the file found
    none) and returns hard-coded records with `actual: None` always -- it
    is a stub, not a live fetch. `api/providers/fred_provider.py` (Phase
    65) supplies real historical actuals only, no consensus/forecast field
    (confirmed directly in Phase 87 and re-confirmed here). The only
    forecast-bearing records anywhere in the repository are
    `macro_intelligence_engine.py`'s small (27-entry) illustrative seed
    dataset, not a multi-year archive. Verdict: `CONSENSUS_DATA_UNAVAILABLE`
    -- per the master prompt's explicit rule, NOT fabricated from actual-
    minus-previous or any other substitute.
  * Tier 2 (macro with reliable timestamps sufficient for a legitimate
    surprise): same root cause, same verdict.
  * Tier 3 (independent cross-market data) -- AVAILABLE, and used here.
    `yfinance` is already a repository dependency (Phase 69-73 ingestion,
    zero new credentials, zero cost, no new account) and supplies real,
    independent (different vendor: Yahoo Finance, sourcing ICE/CBOE/CME
    data, NOT the MT5 broker feed) daily historical data for the US Dollar
    Index (DX-Y.NYB), the VIX (^VIX), the US 10-Year Treasury yield
    (^TNX), COMEX gold futures (GC=F), and WTI crude futures (CL=F) --
    verified empirically to cover 2022-01 through 2026-09 (~1170 daily
    bars each), spanning the entire Phase 83 discovery/confirmation
    window. This is the ONE new dataset acquired in this phase -- fetched
    once, snapshotted into the existing generic artifact store
    (`historical_data_store.save_artifact`), and never silently
    re-fetched (a stale/changed live value on a later re-run would break
    determinism) -- reuse the persisted snapshot on every subsequent run.
  * Tier 4 (order flow) -- reused verbatim from Phase 84/85's own
    findings: `DATA_SOURCE_UNAVAILABLE`, not re-audited.

Causal timestamp contract for the Tier-3 daily external data (master
prompt Sec.10): a daily bar dated D is treated as known no earlier than
D+1 day, 00:00 UTC -- a deliberately conservative buffer (real US-market
daily closes are typically ~20:00-22:00 UTC, but exact settlement-vs-
session timing varies by symbol/exchange/DST, and this repo has no
authoritative per-symbol close-timestamp table) rather than a precise
per-symbol close time. This can only make the feature LESS available (a
few extra same-day 15m bars excluded), never more -- a conservative,
disclosed choice, not an attempt to maximize sample.

Six pre-registered candidates (never expanded after seeing a result; each
with its own economic hypothesis and its own target instrument(s), per the
master prompt's explicit "no data graveyard" rule): DXY-direction and
UST10Y-direction (all 6 canonical instruments, USD-base/quote sign
convention), VIX risk-off on AUDJPY and on XAUUSD (safe-haven hypothesis,
opposite signs), COMEX gold futures leading MT5 spot XAUUSD (cross-venue
lead-lag), and WTI crude leading USDCAD (petrocurrency hypothesis).

Reused, unchanged: Phase 83's frozen Strong Context Baseline / T1 target /
discovery-confirmation dates / Ridge model family; Phase 76's block-
bootstrap and cost proxy; Phase 81's delta-CI bootstrap; Phase 86's
cost-scenario and plateau conventions; Phase 87's data-source-
independence disclosure discipline and researcher-degree-of-freedom
ledger pattern.

Read-only research. No execution/broker/risk import. No entries, exits,
position sizing, or automation exist anywhere in this module. The frozen
Phase-74 Gold holdout is never read.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase76_event_study as p76
import phase83_conditional_interaction_discovery as p83
import phase84_information_frontier_audit as p84
import phase86_aggressive_edge_discovery as p86
from phase76_event_study import RANDOM_SEED, _COST_ATR_PROXY
from phase81_v2_information_decomposition import bootstrap_delta_ci
from phase82_compression_expansion_ml_pilot import _r2_fn
from phase83_conditional_interaction_discovery import (
    BASELINE_D_COLUMNS, INSTRUMENTS_83, PRIMARY_HORIZON, PRIMARY_TF,
    discovery_confirmation_split, fit_and_eval_83,
)

SCHEMA_VERSION = "phase88.1"
ARTIFACT_KEY = "phase88_external_information_edge_hunt"
_EXTERNAL_SNAPSHOT_KEY = "phase88_external_market_data_snapshot"

_MATERIAL_R2_MARGIN = 0.01
_MIN_CELL_N = 200
_AVAILABILITY_LAG_DAYS = 1     # conservative causal buffer, see module docstring
_TIER3_SYMBOLS: Dict[str, str] = {
    "DXY": "DX-Y.NYB", "VIX": "^VIX", "UST10Y": "^TNX", "GOLD_FUT": "GC=F", "CRUDE_FUT": "CL=F",
}
COST_SCENARIOS: Dict[str, float] = dict(p86.COST_SCENARIOS)   # reused unchanged: BASE/ADVERSE/SEVERE


# ==========================================================================
# Priority 1/2 (Tier 1/2) -- economic-surprise & macro-with-timestamps
# feasibility audit (never fabricated, per Sec.5)
# ==========================================================================
def economic_surprise_feasibility() -> Dict[str, Any]:
    import inspect as _inspect
    import xauusd_daily_preflight as preflight
    ff_src = _inspect.getsource(preflight.ForexFactoryProvider)
    ff_has_network_call = any(tok in ff_src for tok in ("requests.", "urllib", "httpx", "http.client"))
    ff_actual_always_none = "\"actual\": None" in ff_src or "'actual': None" in ff_src
    return {
        "tier": "1/2 (economic surprise / macro-with-timestamps)",
        "forex_factory_provider_makes_a_live_network_call": ff_has_network_call,
        "forex_factory_provider_actual_field_hardcoded_none": ff_actual_always_none,
        "note": "xauusd_daily_preflight.ForexFactoryProvider.get_calendar() was inspected by "
                   "source: it contains no requests/urllib/httpx call anywhere and its records' "
                   "'actual' field is hard-coded None -- it is a stub returning illustrative "
                   "forecast/previous values, never a live historical fetch. api/providers/"
                   "fred_provider.py (Phase 65) supplies real actuals only, no consensus field "
                   "(re-confirmed from Phase 87). macro_intelligence_engine.py's forecast-bearing "
                   "records are a 27-entry illustrative seed, not a historical archive.",
        "verdict": "CONSENSUS_DATA_UNAVAILABLE",
        "reason": "No historically-timestamped, multi-year, forecast-bearing economic release "
                   "archive exists in this repository or any already-integrated connector. Per "
                   "the master prompt's explicit rule, this is documented rather than "
                   "reconstructed from actual-minus-previous or any other substitute.",
    }


def order_flow_feasibility() -> Dict[str, Any]:
    """Reused verbatim from Phase 84/85 -- never re-audited."""
    audit = dict(p84.MT5_CAPABILITY_AUDIT)
    audit["tier"] = "4 (order flow / microstructure)"
    audit["verdict"] = "DATA_SOURCE_UNAVAILABLE"
    audit["reason"] = "Reused from Phase 84/85's own findings: no historical tick data has ever " \
                      "been ingested and no bid/ask/spread/depth field exists in the schema."
    return audit


# ==========================================================================
# Tier 3 -- independent cross-market data acquisition (the one new dataset)
# ==========================================================================
def acquire_external_snapshot() -> Dict[str, Any]:
    """Fetches once via yfinance (already a repository dependency, free, no
    new credentials) and persists a durable snapshot. Never called again
    once a snapshot exists -- run() always prefers the persisted one, so
    results stay deterministic across time even though the live data
    could change or Yahoo could later revise history."""
    import yfinance as yf
    series: Dict[str, List[Dict[str, Any]]] = {}
    for name, symbol in _TIER3_SYMBOLS.items():
        df = yf.download(symbol, start="2016-01-01", end="2026-09-04", interval="1d", progress=False)
        if df.empty:
            series[name] = []
            continue
        close = df["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        rows = [{"date": ts.strftime("%Y-%m-%d"), "close": float(v)}
               for ts, v in close.items() if np.isfinite(v)]
        series[name] = rows
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Yahoo Finance (yfinance)", "symbols": dict(_TIER3_SYMBOLS),
        "data_source_independence": "Independent -- different vendor (Yahoo Finance, sourcing "
                                   "ICE/CBOE/CME data) than the MT5 broker feed used by every "
                                   "other phase's data.",
        "timestamp_semantics": "One row per UTC calendar date, Yahoo Finance daily close. "
                              "Availability lag applied downstream: a bar dated D is treated as "
                              f"known no earlier than D+{_AVAILABILITY_LAG_DAYS} day(s), 00:00 UTC.",
        "series": series,
    }
    store.save_artifact(_EXTERNAL_SNAPSHOT_KEY, "phase88_external_market_data_snapshot", payload)
    return payload


def get_external_snapshot() -> Dict[str, Any]:
    art = store.load_artifact(_EXTERNAL_SNAPSHOT_KEY)
    if art and art.get("payload", {}).get("series"):
        return art["payload"]
    return acquire_external_snapshot()


def _external_series_causal(name: str, snapshot: Dict[str, Any]) -> pd.Series:
    """Causal daily log-return series for one external symbol, indexed by
    the timestamp from which it becomes available (date + lag, 00:00 UTC)."""
    rows = snapshot["series"].get(name, [])
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").drop_duplicates("date")
    ret = np.log(df["close"].to_numpy(float) / df["close"].shift(1).to_numpy(float))
    available_at = df["date"] + pd.Timedelta(days=_AVAILABILITY_LAG_DAYS)
    s = pd.Series(ret, index=available_at, name=name)
    return s[np.isfinite(s.to_numpy(float))]


def merge_external_onto_dataset(ds: pd.DataFrame, name: str, snapshot: Dict[str, Any],
                                sign: float = 1.0) -> pd.DataFrame:
    """Causal as-of (backward) merge: each row gets the most recent
    external observation whose availability timestamp is <= its own
    prediction_timestamp. A row with no qualifying external observation
    yet (e.g. before the external series' own history begins) is dropped,
    never filled with a future or default value."""
    ext = _external_series_causal(name, snapshot)
    if ext.empty:
        out = ds.copy()
        out[f"feat__ext_{name.lower()}"] = np.nan
        return out.dropna(subset=[f"feat__ext_{name.lower()}"])
    ext_df = ext.reset_index()
    ext_df.columns = ["available_at", "value"]
    ext_df["available_at"] = pd.to_datetime(ext_df["available_at"], utc=True).astype("datetime64[us, UTC]")
    left = ds.sort_values("prediction_timestamp").reset_index(drop=True).copy()
    left["prediction_timestamp"] = pd.to_datetime(
        left["prediction_timestamp"], utc=True).astype("datetime64[us, UTC]")
    merged = pd.merge_asof(left, ext_df.sort_values("available_at"),
                           left_on="prediction_timestamp", right_on="available_at",
                           direction="backward")
    col = f"feat__ext_{name.lower()}"
    merged[col] = merged["value"].to_numpy(float) * sign
    merged = merged.drop(columns=["available_at", "value"])
    merged = merged.dropna(subset=[col]).reset_index(drop=True)
    n = len(merged)
    v = merged[col].to_numpy(float)
    rank = np.full(n, np.nan)
    w = min(200, n)
    if n >= 20:
        sw = np.lib.stride_tricks.sliding_window_view(v, w)
        rank[w - 1:] = (sw <= sw[:, -1:]).mean(axis=1)
    merged[f"{col}_rank"] = rank
    return merged.dropna(subset=[f"{col}_rank"]).reset_index(drop=True)


# ==========================================================================
# pre-registered candidate registry (six, frozen, never expanded)
# ==========================================================================
# DXY/UST10Y targets are restricted to the 4 instruments with a direct,
# standard USD-repricing hypothesis (USDJPY = USD base; EURUSD/GBPUSD = USD
# quote; XAUUSD = USD-denominated) -- GBPJPY and AUDJPY are excluded from
# E1/E2 as JPY/AUD crosses with no clean direct-DXY story (master prompt
# Sec.7: "if a dataset has no clear economic hypothesis, do not prioritize
# it"); AUDJPY instead gets its own clean hypothesis under E3 (VIX).
_SIGN_BY_TARGET_DXY_TNX: Dict[str, float] = {
    "USDJPY": +1.0, "EURUSD": -1.0, "GBPUSD": -1.0, "XAUUSD": -1.0,
}

EXTERNAL_CANDIDATES: Tuple[Dict[str, Any], ...] = (
    {"id": "E1_DXY_direction", "series": "DXY", "targets": tuple(_SIGN_BY_TARGET_DXY_TNX.keys()),
     "sign_map": dict(_SIGN_BY_TARGET_DXY_TNX),
     "hypothesis": "US Dollar Index daily return predicts next-period FX/gold direction via USD "
                  "repricing (USDJPY/EURUSD/GBPUSD/XAUUSD only -- see target-restriction note)."},
    {"id": "E2_UST10Y_direction", "series": "UST10Y", "targets": tuple(_SIGN_BY_TARGET_DXY_TNX.keys()),
     "sign_map": dict(_SIGN_BY_TARGET_DXY_TNX),
     "hypothesis": "US 10-Year Treasury yield change predicts FX/gold direction via rate-"
                  "differential repricing (same target restriction and reasoning as E1)."},
    {"id": "E3_VIX_riskoff_AUDJPY", "series": "VIX", "targets": ("AUDJPY",), "sign_map": {"AUDJPY": -1.0},
     "hypothesis": "A VIX spike (risk-off) predicts AUDJPY weakness (risk-sensitive carry pair)."},
    {"id": "E4_VIX_riskoff_XAUUSD", "series": "VIX", "targets": ("XAUUSD",), "sign_map": {"XAUUSD": +1.0},
     "hypothesis": "A VIX spike (risk-off) predicts XAUUSD strength (safe-haven demand)."},
    {"id": "E5_GOLDFUT_leads_XAUUSD", "series": "GOLD_FUT", "targets": ("XAUUSD",), "sign_map": {"XAUUSD": +1.0},
     "hypothesis": "COMEX gold futures returns lead MT5 spot XAUUSD (cross-venue lead-lag)."},
    {"id": "E6_CRUDEFUT_leads_USDCAD", "series": "CRUDE_FUT", "targets": ("USDCAD",), "sign_map": {"USDCAD": -1.0},
     "hypothesis": "WTI crude oil returns predict USDCAD direction (petrocurrency hypothesis)."},
)


def evaluate_external_candidate(candidate: Dict[str, Any], snapshot: Dict[str, Any],
                                target_col: str = "T1") -> Dict[str, Any]:
    frames = []
    for inst in candidate["targets"]:
        base_ds = p83.build_context_dataset(inst, PRIMARY_TF, PRIMARY_HORIZON)
        if base_ds.empty:
            continue
        sign = candidate["sign_map"].get(inst, 1.0)
        merged = merge_external_onto_dataset(base_ds, candidate["series"], snapshot, sign=sign)
        if not merged.empty:
            frames.append(merged)
    if not frames:
        return {"candidate_id": candidate["id"], "state": "NO_DATA"}
    pooled = pd.concat(frames, ignore_index=True).sort_values("prediction_timestamp").reset_index(drop=True)
    discovery, confirmation = discovery_confirmation_split(pooled)
    if len(discovery) < _MIN_CELL_N or len(confirmation) < _MIN_CELL_N:
        return {"candidate_id": candidate["id"], "state": "INSUFFICIENT_SAMPLE",
               "n_discovery": len(discovery), "n_confirmation": len(confirmation)}

    ext_col = f"feat__ext_{candidate['series'].lower()}"
    baseline_cols = [f"feat__{c}" for c in BASELINE_D_COLUMNS]
    m0 = fit_and_eval_83(discovery, confirmation, baseline_cols, target_col)
    m1 = fit_and_eval_83(discovery, confirmation, baseline_cols + [ext_col], target_col)
    m2 = fit_and_eval_83(discovery, confirmation, baseline_cols + [f"{ext_col}_rank"], target_col)
    boot_raw = bootstrap_delta_ci(m0["_y_true"], m1["_p_pred"], m0["_p_pred"], _r2_fn(m0["train_mean"]),
                                  block=PRIMARY_HORIZON, seed=RANDOM_SEED)
    boot_rank = bootstrap_delta_ci(m0["_y_true"], m2["_p_pred"], m0["_p_pred"], _r2_fn(m0["train_mean"]),
                                   block=PRIMARY_HORIZON, seed=RANDOM_SEED)

    # placebo: shuffle the external feature within discovery+confirmation
    rng = np.random.default_rng(hash(candidate["id"]) % (2 ** 31))
    disc_shuf, conf_shuf = discovery.copy(), confirmation.copy()
    disc_shuf[f"{ext_col}_rank"] = rng.permutation(disc_shuf[f"{ext_col}_rank"].to_numpy())
    conf_shuf[f"{ext_col}_rank"] = rng.permutation(conf_shuf[f"{ext_col}_rank"].to_numpy())
    m2p = fit_and_eval_83(disc_shuf, conf_shuf, baseline_cols + [f"{ext_col}_rank"], target_col)
    boot_placebo = bootstrap_delta_ci(m0["_y_true"], m2p["_p_pred"], m0["_p_pred"],
                                      _r2_fn(m0["train_mean"]), block=PRIMARY_HORIZON, seed=RANDOM_SEED)

    return {"candidate_id": candidate["id"], "hypothesis": candidate["hypothesis"],
           "targets": list(candidate["targets"]), "n_discovery": int(len(discovery)),
           "n_confirmation": int(len(confirmation)), "baseline_r2": m0["metrics"]["oos_r2"],
           "delta_r2_raw": boot_raw, "delta_r2_rank": boot_rank, "placebo_delta_r2": boot_placebo}


def classify_candidate_verdict(result: Dict[str, Any]) -> Tuple[str, str]:
    if result.get("state") in ("NO_DATA", "INSUFFICIENT_SAMPLE"):
        return "DATA_SOURCE_UNAVAILABLE", result.get("state")
    delta = result["delta_r2_rank"]
    point, excl = delta.get("point"), delta.get("excludes_zero")
    if point is None or not excl or point <= 0:
        return "NO_EXTERNAL_INFORMATION_FOUND", "Delta R^2 not CI-excluding positive."
    if abs(result["placebo_delta_r2"].get("point") or 0) >= point:
        return "LEAKAGE", "Placebo (shuffled external feature) did not collapse relative to the real effect."
    if point < _MATERIAL_R2_MARGIN:
        return "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE", \
            f"Delta {point} below the {_MATERIAL_R2_MARGIN} materiality margin."
    return "PROMISING_TRADING_HYPOTHESIS", f"Material, CI-excluding, placebo-collapsing delta of {point}."


# ==========================================================================
# researcher-degree-of-freedom ledger
# ==========================================================================
class ResearchLedger88:
    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def record(self, stage: str, hypothesis_id: str, description: str, outcome: str,
              reason: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        self.entries.append({"stage": stage, "hypothesis_id": hypothesis_id, "description": description,
                            "outcome": outcome, "reason": reason, "metrics": metrics or {}})

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self.entries)


_VALID_VERDICTS = ("NO_EXTERNAL_INFORMATION_FOUND", "EXTERNAL_INFORMATION_FOUND_BUT_NOT_DIRECTIONAL",
                  "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE", "POSITIVE_EXPECTANCY_BUT_FRAGILE",
                  "PROMISING_TRADING_HYPOTHESIS", "ROBUST_EDGE_CANDIDATE", "ROBUST_TRADING_EDGE",
                  "DATA_SOURCE_UNAVAILABLE", "LEAKAGE", "OVERFIT", "REJECTED")


def final_decision(candidate_results: List[Dict[str, Any]], candidate_verdicts: Dict[str, str]) -> Tuple[str, str]:
    promoted = [cid for cid, v in candidate_verdicts.items() if v == "PROMISING_TRADING_HYPOTHESIS"]
    if promoted:
        return "PROMISING_TRADING_HYPOTHESIS", \
            f"{len(promoted)} candidate(s) cleared discovery/confirmation/placebo/materiality: {promoted}."
    any_directional_not_actionable = any(v == "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE"
                                         for v in candidate_verdicts.values())
    if any_directional_not_actionable:
        return "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE", \
            "At least one Tier-3 candidate shows a real but sub-material effect; none is economically actionable."
    return "NO_EXTERNAL_INFORMATION_FOUND", \
        ("None of the six pre-registered Tier-3 external candidates (DXY, UST10Y, VIX x2, gold "
         "futures, crude futures) produced a material, CI-excluding, placebo-surviving directional "
         "effect on their hypothesized target instrument(s). Tier 1/2 (economic surprise) remain "
         "CONSENSUS_DATA_UNAVAILABLE and Tier 4 (order flow) remains DATA_SOURCE_UNAVAILABLE.")


# ==========================================================================
# result container
# ==========================================================================
@dataclass
class Phase88Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    tier1_2_economic_surprise: Dict[str, Any]
    tier4_order_flow: Dict[str, Any]
    external_data_provenance: Dict[str, Any]
    candidate_registry: List[Dict[str, Any]]
    candidate_results: Dict[str, Any]
    candidate_verdicts: Dict[str, str]
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


def run() -> Phase88Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()
    ledger = ResearchLedger88()

    tier12 = economic_surprise_feasibility()
    tier4 = order_flow_feasibility()
    ledger.record("tier1_2_audit", "economic_surprise", "Genuine actual-vs-consensus surprise study",
                 tier12["verdict"], tier12["reason"])
    ledger.record("tier4_audit", "order_flow", "Historical tick-level order-flow information",
                 tier4["verdict"], tier4["reason"])

    snapshot = get_external_snapshot()
    provenance = {"provider": snapshot["provider"], "symbols": snapshot["symbols"],
                 "data_source_independence": snapshot["data_source_independence"],
                 "timestamp_semantics": snapshot["timestamp_semantics"],
                 "fetched_at": snapshot["fetched_at"],
                 "n_daily_rows_per_symbol": {k: len(v) for k, v in snapshot["series"].items()}}

    results_1 = {c["id"]: evaluate_external_candidate(c, snapshot, "T1") for c in EXTERNAL_CANDIDATES}
    results_2 = {c["id"]: evaluate_external_candidate(c, snapshot, "T1") for c in EXTERNAL_CANDIDATES}
    determinism_match = (results_1 == results_2)

    verdicts: Dict[str, str] = {}
    for c in EXTERNAL_CANDIDATES:
        cid = c["id"]
        v, reason = classify_candidate_verdict(results_1[cid])
        verdicts[cid] = v
        ledger.record("candidate_evaluation", cid, c["hypothesis"], v, reason,
                     metrics={k: val for k, val in results_1[cid].items()
                             if k not in ("hypothesis",)})

    verdict, verdict_reason = final_decision(list(results_1.values()), verdicts)

    ident = json.dumps({"schema": SCHEMA_VERSION, "verdicts": verdicts, "verdict": verdict},
                      sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase88Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(INSTRUMENTS_83), timeframe=PRIMARY_TF,
        tier1_2_economic_surprise=tier12, tier4_order_flow=tier4, external_data_provenance=provenance,
        candidate_registry=[{k: v for k, v in c.items()} for c in EXTERNAL_CANDIDATES],
        candidate_results=results_1, candidate_verdicts=verdicts, research_ledger=ledger.to_list(),
        verdict=verdict, verdict_reason=verdict_reason, determinism={"match": determinism_match},
        runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase88Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase88_external_information_edge_hunt", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 88 - external information acquisition & aggressive directional edge hunt ...",
         flush=True)
    res = run()
    print(f"\n=== PHASE 88 ({res.runtime_seconds}s) ===")
    print(f"External data provenance: {json.dumps(res.external_data_provenance, default=str)}")
    print(f"\nTier 1/2: {json.dumps(res.tier1_2_economic_surprise, default=str)}")
    print(f"\nTier 4: {json.dumps(res.tier4_order_flow, default=str)}")
    for cid, r in res.candidate_results.items():
        print(f"\n{cid}: {json.dumps(r, default=str)}")
    print(f"\nVerdicts: {json.dumps(res.candidate_verdicts, default=str)}")
    print(f"\nDeterminism: {res.determinism}")
    print(f"\nFINAL VERDICT: {res.verdict} -- {res.verdict_reason}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "EXTERNAL_CANDIDATES", "COST_SCENARIOS",
    "economic_surprise_feasibility", "order_flow_feasibility", "acquire_external_snapshot",
    "get_external_snapshot", "merge_external_onto_dataset", "evaluate_external_candidate",
    "classify_candidate_verdict", "ResearchLedger88", "final_decision",
    "run", "persist", "get_result", "main",
]
