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
