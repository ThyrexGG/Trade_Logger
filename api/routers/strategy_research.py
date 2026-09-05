# -*- coding: utf-8 -*-
"""
FastAPI Strategy Research Router (Phase 69) — read-only.

Phase 69 surface:
  GET /api/research/historical/coverage  — what the persistent OHLCV store holds
  GET /api/research/universe              — the research instrument universe
  GET /api/research/gold-baseline         — the recovered previous Gold discovery

No mutation endpoints. No execution / broker / risk import. Every number is
produced by the authoritative Python engines and merely serialized.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

import gold_strategy_baseline
import historical_data_store as store
import research_universe
from api.schemas import GoldBaselineResponse, HistoricalCoverageResponse

router = APIRouter(prefix="/api/research", tags=["Strategy Research"])

_SAFETY = {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}


@router.get("/historical/coverage", response_model=HistoricalCoverageResponse)
def get_historical_coverage() -> HistoricalCoverageResponse:
    """Persistent OHLCV store coverage + per-instrument/timeframe sufficiency."""
    available = store.list_available()
    sufficiency = []
    for inst in research_universe.universe():
        for tf in ("1d", "1h", "4h"):
            sufficiency.append(store.data_sufficiency(inst.symbol, tf))
    return HistoricalCoverageResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        universe=list(research_universe.RESEARCH_UNIVERSE),
        timeframes=list(research_universe.CANONICAL_TIMEFRAMES),
        data_capable_timeframes=["1h", "4h", "1d"],
        available=available,
        sufficiency=sufficiency,
        notes=research_universe.TIMEFRAME_DATA_NOTE,
        safety_barrier=_SAFETY,
    )


@router.get("/data-coverage")
def get_data_coverage() -> Dict[str, Any]:
    """Phase 73 — the full instrument x timeframe coverage report with
    SUFFICIENT / PARTIAL / INSUFFICIENT_DATA / PROVIDER_UNAVAILABLE / NO_DATA."""
    import data_coverage
    rep = data_coverage.coverage_report()
    rep["safety_barrier"] = _SAFETY
    return rep


@router.get("/historical/providers")
def get_historical_providers() -> Dict[str, Any]:
    """Phase 73 — historical intraday provider capabilities (no credentials)."""
    import historical_provider
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_provider": historical_provider.get_provider().name,
        "capabilities": historical_provider.list_capabilities(),
        "config_pattern": {
            "env": ["HISTORICAL_OHLCV_PROVIDER", "HISTORICAL_OHLCV_API_KEY"],
            "note": "key is read server-side only — never returned to the frontend, "
                    "never in artifacts, never in AI context",
        },
        "safety_barrier": _SAFETY,
    }


@router.get("/dataset-manifest")
def get_dataset_manifest(symbol: str = "XAUUSD") -> Dict[str, Any]:
    """Phase 74 — provenance manifest for a research dataset: which provider,
    which vendor symbol, date range, candle count, quality, licensing, and an
    explicit holdout-isolation statement. `NOT_BUILT` until
    `python -m dataset_manifest <SYMBOL>` has run."""
    import dataset_manifest
    m = dataset_manifest.get_manifest(symbol)
    if not m:
        return {"state": "NOT_BUILT", "symbol": symbol,
                "reason": f"run `python -m dataset_manifest {symbol}`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    m["state"] = "AVAILABLE"
    m["safety_barrier"] = _SAFETY
    return m


@router.get("/gold-revalidation/native")
def get_native_gold_revalidation() -> Dict[str, Any]:
    """Phase 73 — native / near-native XAUUSD revalidation (1m/5m/15m), each
    result labelled NATIVE / NEAR_NATIVE / PROXY. `NOT_COMPUTED` until
    `python -m native_gold_revalidation` has run."""
    import native_gold_revalidation
    art = native_gold_revalidation.get_native_revalidation()
    if not art:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m native_gold_revalidation`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    art["state"] = "AVAILABLE"
    art["safety_barrier"] = _SAFETY
    return art


@router.get("/universe")
def get_universe() -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instruments": [
            {
                "symbol": i.symbol, "display": i.display, "category": i.category,
                "yf_symbol": i.yf_symbol, "pip_size": i.pip_size,
                "quote_ccy": i.quote_ccy, "sessions": list(i.sessions), "note": i.note,
            }
            for i in research_universe.universe()
        ],
        "safety_barrier": _SAFETY,
    }


@router.get("/gold-baseline", response_model=GoldBaselineResponse)
def get_gold_baseline() -> GoldBaselineResponse:
    try:
        b = gold_strategy_baseline.get_gold_baseline()
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"baseline unavailable: {e!r}")
    d = b.to_dict()
    d["safety_barrier"] = _SAFETY
    # Phase 73 — surface the native/near-native attempt alongside the Phase-71 proxy
    try:
        import native_gold_revalidation
        nat = native_gold_revalidation.get_native_revalidation()
        if nat:
            d["native_revalidation"] = {
                "native_verdict": nat.get("native_verdict"),
                "edge_status": nat.get("edge_status"),
                "dataset_manifest_id": nat.get("dataset_manifest_id"),
                "approximation_note": nat.get("approximation_note"),
                "per_timeframe": [
                    {k: r.get(k) for k in ("timeframe", "role", "state", "data_tier",
                                           "stored_span_days", "stored_bars", "provider_state",
                                           "vendor_symbol", "oos_metrics")}
                    for r in nat.get("per_timeframe", [])
                ],
                "caveat": nat.get("caveat"),
            }
    except Exception:
        pass
    return GoldBaselineResponse(**d)


# ---------------------------------------------------------------------------
# Phase 70 — strategy definitions & pair ranking (read the persisted artifact;
# discovery compute is an offline CLI, never an API request)
# ---------------------------------------------------------------------------
@router.get("/strategies")
def get_strategies() -> Dict[str, Any]:
    import strategy_discovery
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategies": strategy_discovery.list_strategy_definitions(),
        "timeframe_stack": strategy_discovery.TF_STACK,
        "execution_assumptions": strategy_discovery._assumptions(0.0, 0.0),
        "safety_barrier": _SAFETY,
    }


@router.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str) -> Dict[str, Any]:
    import pair_ranking
    import strategy_discovery
    sdef = strategy_discovery.get_strategy_definition(strategy_id)
    if sdef is None:
        raise HTTPException(status_code=404, detail=f"unknown strategy '{strategy_id}'")
    ranking = pair_ranking.get_pair_ranking()
    per_pair = []
    pair_stability = None
    if ranking:
        per_pair = [c for c in ranking.get("candidates", []) if c.get("strategy_id") == strategy_id]
        pair_stability = ranking.get("pair_stability", {}).get(strategy_id)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "definition": sdef.to_dict(),
        "per_pair_results": per_pair,
        "pair_stability": pair_stability,
        "ranking_generated_at": ranking.get("generated_at") if ranking else None,
        "safety_barrier": _SAFETY,
    }


@router.get("/gold-revalidation")
def get_gold_revalidation() -> Dict[str, Any]:
    """The Phase-71 XAUUSD revalidation artifact (1h/1d proxy for the frozen 1m
    contract). `NOT_COMPUTED` until `python -m gold_revalidation` has run."""
    import gold_revalidation
    reval = gold_revalidation.get_revalidation()
    if not reval:
        return {
            "state": "NOT_COMPUTED",
            "reason": "no revalidation artifact yet — run `python -m gold_revalidation`",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "safety_barrier": _SAFETY,
        }
    reval["state"] = "AVAILABLE"
    reval["safety_barrier"] = _SAFETY
    return reval


@router.get("/pair-ranking")
def get_pair_ranking() -> Dict[str, Any]:
    import pair_ranking
    ranking = pair_ranking.get_pair_ranking()
    if not ranking:
        return {
            "state": "NOT_COMPUTED",
            "reason": "no pair-ranking artifact yet — run `python -m pair_ranking --timeframe 1h`",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "leaderboard": [], "candidates": [], "safety_barrier": _SAFETY,
        }
    ranking["state"] = "AVAILABLE"
    ranking["safety_barrier"] = _SAFETY
    return ranking


@router.get("/diagnostic-matrix")
def get_diagnostic_matrix() -> Dict[str, Any]:
    """The research diagnostic matrix: per (instrument x strategy x segmentation
    dimension x bucket) N / expectancy / bootstrap CI / sample class / status,
    with multiple-comparison accounting and a candidate promotion gate.
    `NOT_COMPUTED` until `python -m research_diagnostics 15m` has run.
    Diagnosis only — never a trading recommendation."""
    import research_diagnostics
    m = research_diagnostics.get_matrix()
    if not m:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m research_diagnostics 15m`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    m["state"] = "AVAILABLE"
    m["safety_barrier"] = _SAFETY
    return m


@router.get("/orb-vwap")
def get_orb_vwap_research() -> Dict[str, Any]:
    """Phase 75 — ORB v1 + VWAP v1 systematic strategy research: the 6-instrument
    x 2-strategy results matrix (N / E[R] / PF / win rate / CI / max DD / status),
    aggregates, multiple-comparison accounting, candidate promotion gate and
    verdict. `NOT_COMPUTED` until `python -m phase75_orb_vwap` has run.
    Research only — never a trading recommendation; no candidate is 'validated'."""
    import phase75_orb_vwap
    r = phase75_orb_vwap.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase75_orb_vwap`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/large-bar-reversal")
def get_large_bar_reversal_validation() -> Dict[str, Any]:
    """Phase 77 — large-bar reversal candidate validation: the H8 phenomenon from
    Phase 76 taken to a realistic execution model. Primary hypotheses H8-P1..P4
    (all pairs / JPY crosses / ranging regime / cost stress) with dev vs OOS
    metrics, deterministic bootstrap CIs, an ATR cost-sensitivity grid, regime /
    volatility / session conditioning, a small parameter neighbourhood, the
    cross-asset class, per-hypothesis candidate gates and the Phase 78 decision.
    `NOT_COMPUTED` until `python -m phase77_large_bar_reversal` has run.
    Research only — no candidate here is a validated or deployable trading edge."""
    import phase77_large_bar_reversal
    r = phase77_large_bar_reversal.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase77_large_bar_reversal`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/market-behavior-discovery-ii")
def get_market_behavior_discovery_ii() -> Dict[str, Any]:
    """Phase 78 — literature-guided market behavior discovery II: momentum x
    volatility-expansion x breakout/retest x session-transitions. Hypothesis
    registry, dev/OOS scorecard with block-bootstrap CIs, null-control
    placebo effects, multiple-testing tiers, cost sensitivity, candidate gate,
    ML-readiness scorecard, negative-knowledge registry (carrying Phase 77's
    large-bar reversal forward) and final verdict.
    `NOT_COMPUTED` until `python -m phase78_market_behavior_discovery_ii` has
    run. Research only — no phenomenon here is a validated trading edge."""
    import phase78_market_behavior_discovery_ii
    r = phase78_market_behavior_discovery_ii.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase78_market_behavior_discovery_ii`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/ml-target-integrity")
def get_ml_target_integrity() -> Dict[str, Any]:
    """Phase 79 — ML target integrity, leakage audit & pilot readiness: formal
    versioned target specifications for Phase 78's two ML_TARGET_READY findings
    (V2 high-volatility regime persistence, V1 15m compression-duration range
    expansion), feature/target timestamp-ordering audit, a static rolling-
    window leakage scan, future-shock / past-shift adversarial regression
    tests, a stable-ATR contamination re-check, rolling-window overlap and
    effective-sample-size estimates, purge/embargo analysis, placebo-control
    decoupling (plus the documented mean-invariance-of-permutation finding),
    leave-one-asset-out and cross-year period stability, and a per-target
    TARGET_INTEGRITY_READY / TARGET_REQUIRES_REVISION / TARGET_REJECTED gate.
    `NOT_COMPUTED` until `python -m phase79_ml_target_integrity` has run.
    Research-integrity only — no model is trained here and no target here is
    a trading signal."""
    import phase79_ml_target_integrity
    r = phase79_ml_target_integrity.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase79_ml_target_integrity`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/ml-volatility-regime")
def get_ml_volatility_regime_pilot() -> Dict[str, Any]:
    """Phase 80 — ML volatility regime prediction pilot: the first phase
    permitted to train a predictive model. Uses the exact, unchanged Phase
    78/79 V2 target (rv_rank[i+h] > 0.66 after a currently-HIGH bar). Reports
    the feature registry, ablation sweep, full horizon matrix, baselines
    (majority / persistence / simple-volatility / random), walk-forward
    fold-by-fold metrics (each fold's test window IS a calendar-year OOS
    period), cross-asset and leave-one-instrument-out results, permutation
    importance, shuffled-target / placebo / future-shock controls,
    calibration, determinism, the 8-gate evaluation and final verdict.
    `NOT_COMPUTED` until `python -m phase80_ml_volatility_regime` has run.
    Research only: no trading signal, no execution, no model connected to
    any live system."""
    import phase80_ml_volatility_regime
    r = phase80_ml_volatility_regime.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase80_ml_volatility_regime`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/v2-information-decomposition")
def get_v2_information_decomposition() -> Dict[str, Any]:
    """Phase 81 — V2 incremental information / context decomposition: an
    interpretable nested decomposition (current-state -> volatility ->
    time/session -> +price -> +candle/regime -> full) of the Phase 78/79 V2
    target, isolating whether ML's apparent predictive value (Phase 80) is
    genuinely new information or mostly deterministic intraday/session
    seasonality and current volatility state. Logistic regression is the
    primary (interpretable) model throughout; HistGradientBoosting is a
    secondary reference back to Phase 80. Reports conditional-probability
    tables, train-only time/volatility neutralization, cross-asset/cross-
    year/leave-one-out/horizon breakdowns, the corrected population-matched
    placebo (and why the original population-decoupled version was
    confounded), shuffled-target and future-shock/temporal-shift controls,
    block-bootstrap CIs, gates, and one of four controlled verdicts.
    `NOT_COMPUTED` until `python -m phase81_v2_information_decomposition`
    has run. Research only: no trading signal, no execution."""
    import phase81_v2_information_decomposition
    r = phase81_v2_information_decomposition.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase81_v2_information_decomposition`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/v1-compression-expansion")
def get_v1_compression_expansion() -> Dict[str, Any]:
    """Phase 82 — V1 15m compression -> expansion ML pilot: a nested
    regression decomposition (constant -> volatility -> compression ->
    +compression+volatility -> time -> volatility+time -> +compression ->
    +price/range -> full) of the Phase 78/79 V1 target, asking whether
    compression DURATION carries predictive information about subsequent
    range expansion beyond current volatility and time/session structure.
    Ridge is the primary (interpretable) model; RandomForest and
    HistGradientBoosting are secondary reference models. Documents a
    resolved definitional ambiguity (the literal Phase 78 event makes
    duration a constant; this phase uses a documented, minimal extension)
    and a target-centering correction found via the future-shock invariance
    test. Reports duration dose-response, volatility/session/severity/range
    conditioning, train-only residualization, cross-asset/cross-year/leave-
    one-out/horizon breakdowns, matched-placebo/shuffled-target/temporal-
    shift/future-shock controls, block-bootstrap CIs, gates, and one of
    four controlled verdicts. `NOT_COMPUTED` until
    `python -m phase82_compression_expansion_ml_pilot` has run. Research
    only: no trading signal, no execution."""
    import phase82_compression_expansion_ml_pilot
    r = phase82_compression_expansion_ml_pilot.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase82_compression_expansion_ml_pilot`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/conditional-interaction-discovery")
def get_conditional_interaction_discovery() -> Dict[str, Any]:
    """Phase 83 — conditional market structure & regime interaction
    discovery: 5 pre-registered interaction candidates (volatility x trend,
    volatility x session, momentum x volatility, location x trend,
    structure x volatility) tested against a fixed strong-context baseline
    (volatility + session/time + trend + momentum + location + structure)
    across ALL bars of the 6-instrument universe -- NOT reopening V1/V2's
    event-conditioned targets. Reports a discovery/confirmation temporal
    split (confirmation touched once), Benjamini-Hochberg multiple-testing
    correction across the 5 candidates, cross-asset and leave-one-out
    breakdowns, regime/horizon stability, shuffled-target and wrong-context
    placebo controls, temporal-shift diagnostics, block-bootstrap CIs, and
    one of the master prompt's standardized verdicts per candidate.
    `NOT_COMPUTED` until
    `python -m phase83_conditional_interaction_discovery` has run. Research
    only: no trading signal, no execution."""
    import phase83_conditional_interaction_discovery
    r = phase83_conditional_interaction_discovery.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase83_conditional_interaction_discovery`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/information-frontier-audit")
def get_information_frontier_audit() -> Dict[str, Any]:
    """Phase 84 — information frontier & missing signal research audit: an
    audit/roadmap phase, not a pipeline phase. Reports a repository
    information inventory (MT5 tick-volume/tick-data/macro/news/AI
    capabilities, live-verified via `historical_data_store.list_available()`
    for timeframe coverage), a cumulative existing-data feature-group
    ablation for both the magnitude (T2) and direction (T1) targets, a
    small bounded tick-volume ablation with shuffled-target and
    volume-shuffle placebo controls, a feature redundancy/mutual-information/
    PCA audit, a live-synthesized predictability-ceiling table across
    Phases 78/80/81/82/83, an M1/M5 native-resolution feasibility
    assessment, and the 20-row Information Frontier Matrix with the
    standardized six-level verdict vocabulary and P0-P3 priorities. Produces
    NO strategy artifact and NO trading signal -- the deliverable is a
    research report and a single Phase-85 recommendation.
    `NOT_COMPUTED` until `python -m phase84_information_frontier_audit` has
    run. Research only: no trading signal, no execution."""
    import phase84_information_frontier_audit
    r = phase84_information_frontier_audit.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase84_information_frontier_audit`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/tick-volume-confirmation")
def get_tick_volume_confirmation() -> Dict[str, Any]:
    """Phase 85 — tick-volume confirmation, generalization & feed-independence
    study: tries to falsify (not preserve) the Phase 84 screening finding
    that adding causal MT5 tick-volume features to Phase 83's frozen Strong
    Context Baseline improves the forward-range magnitude target (T2).
    Reports the frozen M1-M4 ablation (baseline / +volume_rank /
    +volume_ret_1 / +both), a per-instrument cross-asset breakdown across
    all 6 canonical instruments (never reduced post-hoc), leave-one-asset-out
    generalization, predeclared calendar-quarter temporal stability, the full
    h={1,2,4,8} horizon profile, a volatility/session confounding
    decomposition, a five-part placebo battery (target shuffle, global
    volume shuffle, instrument x session stratified shuffle, predeclared
    temporal misalignment, a stronger within-instrument/time-stratum
    placebo), a data-provenance audit of what MT5 tick_volume actually is,
    a broker/feed-independence feasibility check, and a multiple-testing
    (Benjamini-Hochberg) audit of the researcher degrees of freedom. Produces
    exactly one of the standardized verdicts and an explicit claim-hierarchy
    level (A-D) -- never overclaimed beyond what independent-feed and
    cross-asset evidence actually support. `NOT_COMPUTED` until
    `python -m phase85_tick_volume_confirmation` has run. Research only: no
    trading signal, no execution."""
    import phase85_tick_volume_confirmation
    r = phase85_tick_volume_confirmation.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase85_tick_volume_confirmation`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/aggressive-edge-discovery")
def get_aggressive_edge_discovery() -> Dict[str, Any]:
    """Phase 86 — aggressive trading edge discovery: takes Phase 85's
    confirmed tick-volume magnitude information as an input (never
    repeated) and asks whether it, or a small set of newly pre-registered
    conditional-directional-asymmetry cells, can be converted into an
    actual cost-aware trading edge. Reports a three-way temporal split own
    to this phase (discovery / confirmation / a NEW final holdout distinct
    from the frozen Phase-74 Gold contract, which is never touched), an
    8-cell pre-registered location x regime x volume-state screen for
    directional asymmetry (promoted only if it replicates unchanged on
    confirmation), a momentum + volume-filter trading rule (frozen
    threshold chosen from a predeclared discovery-only grid by a
    plateau-preferring rule, never by argmax), cross-asset/temporal-
    quarter/parameter-perturbation/cost-scenario (BASE/ADVERSE/SEVERE)/
    horizon robustness, a placebo battery, a full research ledger
    disclosing every hypothesis tested (promoted or killed), and one of the
    standardized edge-verdict labels. Produces NO live-execution artifact —
    entries/exits/position-sizing/automation do not exist anywhere in this
    module. `NOT_COMPUTED` until `python -m phase86_aggressive_edge_discovery`
    has run. Research only: no trading signal, no execution."""
    import phase86_aggressive_edge_discovery
    r = phase86_aggressive_edge_discovery.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase86_aggressive_edge_discovery`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/directional-information-frontier")
def get_directional_information_frontier() -> Dict[str, Any]:
    """Phase 87 — directional information frontier: since re-slicing the
    existing OHLC/context feature space (Phase 86) found no directional
    edge, this phase hunts for genuinely NEW information instead. Lane A
    (priority 1) tests a causal trade-weighted USD-strength proxy built
    entirely from the already-owned 11-instrument MT5 basket (explicitly
    logged as same-feed, Class A -- not an independent source) against the
    frozen Phase 83 baseline on the T1 direction target, across all 6
    canonical instruments, 4 horizons, 5 temporal blocks, and a placebo.
    Lane B (magnitude tradeability) is attempted only if Lane A clears its
    promotion gates -- otherwise it is reported as structurally blocked,
    since Phase 86 already showed `sign(mom_4)` is not a valid directional
    setup to condition a volume filter on and no other one survived. Also
    reports live data-availability audits (not experiments) for economic-
    surprise information (FRED supplies actuals only, no consensus
    forecast) and order-flow/microstructure information (reused from Phase
    84/85: no historical tick data, no bid/ask/spread/depth in the schema),
    plus a full research ledger. Produces NO live-execution artifact.
    `NOT_COMPUTED` until `python -m phase87_directional_information_frontier`
    has run. Research only: no trading signal, no execution."""
    import phase87_directional_information_frontier
    r = phase87_directional_information_frontier.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase87_directional_information_frontier`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/external-information-edge-hunt")
def get_external_information_edge_hunt() -> Dict[str, Any]:
    """Phase 88 — external information acquisition & aggressive directional
    edge hunt: acquires ONE genuinely new, independent dataset (Yahoo
    Finance daily DXY / VIX / US 10Y yield / COMEX gold futures / WTI
    crude futures -- a different vendor than the MT5 broker feed, free, no
    new credentials, snapshotted once for determinism) and tests six
    pre-registered, hypothesis-driven candidates against the frozen Phase
    83 baseline on the T1 direction target, each with its own economically
    motivated target instrument(s), a causal availability-lag-enforced
    merge, and a placebo. Also reports live feasibility audits (not
    experiments) for Tier 1/2 economic-surprise data (confirmed
    CONSENSUS_DATA_UNAVAILABLE: FRED supplies actuals only, the
    ForexFactory connector is a stub with no live fetch) and Tier 4
    order-flow data (reused from Phase 84/85: DATA_SOURCE_UNAVAILABLE).
    Produces NO live-execution artifact. `NOT_COMPUTED` until
    `python -m phase88_external_information_edge_hunt` has run. Research
    only: no trading signal, no execution."""
    import phase88_external_information_edge_hunt
    r = phase88_external_information_edge_hunt.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase88_external_information_edge_hunt`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r


@router.get("/market-behavior")
def get_market_behavior_discovery() -> Dict[str, Any]:
    """Phase 76 — literature-guided market behavior discovery: the phenomenon
    scorecard (event studies with dev/OOS block-bootstrap CIs, cross-year and
    regime dependence), multiple-testing tiers, negative-knowledge registry,
    promising-research queue, ML-readiness assessment and final verdict.
    `NOT_COMPUTED` until `python -m phase76_event_study` has run.
    Research only — no phenomenon here is a validated trading edge."""
    import phase76_event_study
    r = phase76_event_study.get_result()
    if not r:
        return {"state": "NOT_COMPUTED",
                "reason": "run `python -m phase76_event_study`",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_barrier": _SAFETY}
    r["state"] = "AVAILABLE"
    r["safety_barrier"] = _SAFETY
    return r
