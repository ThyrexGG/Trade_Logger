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

from fastapi import APIRouter, Request
from pydantic import BaseModel

import tenant
from api import sync_service

router = APIRouter(prefix="/api/system", tags=["System Control"])

_SAFETY = {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}


class SyncAutoToggle(BaseModel):
    auto_enabled: bool


def _sync_payload(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {**sync_service.status(), **(extra or {}), "safety_barrier": _SAFETY}


@router.get("/sync")
def get_sync_status(request: Request) -> Dict[str, Any]:
    """State of the in-process broker-sync service for the calling user: whether
    their auto loop is on, whether a cycle is in progress, and the last run."""
    return _sync_payload(sync_service.status(user_id=tenant.current_user_id()))


@router.post("/sync/run")
def run_sync_now(request: Request) -> Dict[str, Any]:
    """Run one broker-sync cycle now for the calling user (each of their active
    broker connections; the owner falls back to the CAPITAL_* env). Data
    ingestion only — no order is placed. Blocks until the cycle finishes."""
    out = sync_service.run_for_user(tenant.current_user_id(), source="manual")
    return _sync_payload(out)


@router.post("/sync/run-if-stale")
def run_sync_if_stale(request: Request, max_age_minutes: int = 15) -> Dict[str, Any]:
    """Run one cycle for the calling user **only if** their last sync is older
    than ``max_age_minutes`` (clamped 1–240). Deduplicated per user via the
    persisted heartbeat. The frontend calls this once on load."""
    minutes = max(1, min(int(max_age_minutes), 240))
    return _sync_payload(
        sync_service.run_if_stale(minutes * 60, user_id=tenant.current_user_id())
    )


@router.put("/sync")
def set_sync_auto(body: SyncAutoToggle, request: Request) -> Dict[str, Any]:
    """Turn the calling user's background auto-sync loop on or off (persisted)."""
    sync_service.set_auto(bool(body.auto_enabled), user_id=tenant.current_user_id())
    return _sync_payload(sync_service.status(user_id=tenant.current_user_id()))
