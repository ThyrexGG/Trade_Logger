# -*- coding: utf-8 -*-
"""
FastAPI Trade Setup Router (Phase 72) — read-only.

  GET /api/trade-setup/{asset}             — full setup evaluation
  GET /api/trade-setup/{asset}/conditions  — just the condition checklist
  GET /api/trade-setup                     — every universe instrument, compact

No mutation. No execution / broker / risk import. The deterministic
``trade_setup.evaluate_setup`` owns the state; this only serializes it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

import research_universe
import trade_setup as engine

router = APIRouter(prefix="/api/trade-setup", tags=["Trade Setup"])

_SAFETY = {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}


def _parse_as_of(as_of: str | None):
    if not as_of:
        return None
    try:
        return datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"malformed as_of: {as_of!r}")


@router.get("")
def list_setups() -> Dict[str, Any]:
    out = []
    for inst in research_universe.universe():
        s = engine.evaluate_setup(inst.symbol)
        out.append({
            "asset": s.asset, "state": s.state, "direction": s.direction,
            "strategy_id": s.strategy_id, "waiting_for": s.waiting_for,
            "reason": s.reason[:200],
            "oos_expectancy_r": s.strategy_validation.get("oos_expectancy_r"),
        })
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "setups": out,
            "safety_barrier": _SAFETY}


@router.get("/{asset}")
def get_setup(asset: str, as_of: str | None = Query(default=None)) -> Dict[str, Any]:
    if not research_universe.is_in_universe(asset):
        raise HTTPException(status_code=404, detail=f"{asset} not in the research universe")
    s = engine.evaluate_setup(asset, as_of=_parse_as_of(as_of))
    d = s.to_dict()
    d["safety_barrier"] = _SAFETY
    return d


@router.get("/{asset}/conditions")
def get_conditions(asset: str, as_of: str | None = Query(default=None)) -> Dict[str, Any]:
    if not research_universe.is_in_universe(asset):
        raise HTTPException(status_code=404, detail=f"{asset} not in the research universe")
    s = engine.evaluate_setup(asset, as_of=_parse_as_of(as_of))
    return {
        "asset": s.asset, "state": s.state, "as_of": s.as_of,
        "conditions": s.conditions, "failing_conditions": s.failing_conditions,
        "waiting_for": s.waiting_for, "strategy_validation": s.strategy_validation,
        "safety_barrier": _SAFETY,
    }
