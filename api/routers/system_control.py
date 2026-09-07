# -*- coding: utf-8 -*-
"""
FastAPI System Control Router — the in-process broker-sync service.

Drives the sync that keeps the journal / Positions page fresh: "Sync now"
(one cycle) and an auto on/off loop. Data ingestion only — no order is
placed, no automation enabled; execution and broker transmission stay
permanently BLOCKED.

(The old ``/api/system/market-data`` MT5 quote switch was removed once the
local MetaTrader 5 terminals were uninstalled — MT5 is now opt-in via the
``MT5_ENABLED`` env var only, with no UI. See ``mt5_gate``.)
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from api import sync_service

router = APIRouter(prefix="/api/system", tags=["System Control"])

_SAFETY = {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}


class SyncAutoToggle(BaseModel):
    auto_enabled: bool


def _sync_payload(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {**sync_service.status(), **(extra or {}), "safety_barrier": _SAFETY}


@router.get("/sync")
def get_sync_status() -> Dict[str, Any]:
    """State of the in-process broker-sync service: whether the auto loop is on,
    whether a cycle is in progress, and the last run's result."""
    return _sync_payload()


@router.post("/sync/run")
def run_sync_now() -> Dict[str, Any]:
    """Run one broker-sync cycle now (Capital.com trade / position sync, push +
    price alerts). Data ingestion only — no order is placed. Blocks until the
    cycle finishes (a few seconds)."""
    result = sync_service.run_once(source="manual")
    return _sync_payload({"ran": result})


@router.post("/sync/run-if-stale")
def run_sync_if_stale(max_age_minutes: int = 15) -> Dict[str, Any]:
    """Run one cycle **only if** the last sync is older than ``max_age_minutes``
    (clamped 1–240). Deduplicated across tabs / devices / restarts via the
    persisted heartbeat. The frontend calls this once on load so a host that
    sleeps (no always-on loop) still shows fresh broker data on open, without
    every open triggering a redundant cycle. Data ingestion only."""
    minutes = max(1, min(int(max_age_minutes), 240))
    return _sync_payload(sync_service.run_if_stale(minutes * 60))


@router.put("/sync")
def set_sync_auto(body: SyncAutoToggle) -> Dict[str, Any]:
    """Turn the background auto-sync loop on or off (persisted). While it is on
    the standalone auto_sync.py daemon stands down to avoid double-syncing."""
    sync_service.set_auto(bool(body.auto_enabled))
    return _sync_payload()
