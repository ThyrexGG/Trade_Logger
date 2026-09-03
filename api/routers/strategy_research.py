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
