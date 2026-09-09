# -*- coding: utf-8 -*-
"""
FastAPI ingest router (platform plan W9).

A friend on a MetaTrader broker (Exness, IC Markets, a prop firm, ...) runs
``agent/mt5_push_agent.py`` on their own Windows PC. It reads their MT5
terminal and POSTs the raw deal / position / balance snapshot here. The
request is already bound to that user by the auth gate, so every write lands
on their rows and no one else's.

Data ingestion only. This router reconstructs closed trades from deal history
and stores a balance / open-position snapshot. It has no order path and never
touches the frozen execution layer — execution stays permanently BLOCKED.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import database
import mt5_ingest

router = APIRouter(prefix="/api/ingest", tags=["Ingest"])

_SAFETY = {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}


class DealIn(BaseModel):
    model_config = {"extra": "ignore"}
    deal_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(default="", max_length=64)
    type: str = Field(default="", max_length=8)          # BUY | SELL (or "0"/"1")
    volume: float = 0.0
    price: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0
    timestamp: int = 0
    position_id: str = Field(min_length=1, max_length=128)


class PositionIn(BaseModel):
    model_config = {"extra": "ignore"}
    position_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(default="", max_length=64)
    direction: Optional[str] = Field(default=None, max_length=8)
    volume: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    floating_pnl: float = 0.0
    swap: float = 0.0
    open_time: str = Field(default="", max_length=64)


class BalanceIn(BaseModel):
    model_config = {"extra": "ignore"}
    balance: float = 0.0
    equity: float = 0.0
    currency: str = Field(default="USD", max_length=8)


class MT5Payload(BaseModel):
    model_config = {"extra": "forbid"}
    account_id: str = Field(min_length=1, max_length=128)
    agent_version: str = Field(default="", max_length=32)
    balance: Optional[BalanceIn] = None
    positions: Optional[List[PositionIn]] = None
    deals: List[DealIn] = Field(default_factory=list)


@router.get("/mt5/cursor")
def mt5_cursor(account: str, request: Request) -> Dict[str, Any]:
    """The timestamp of the newest deal already stored for this account and
    this user. The agent sends only deals newer than this."""
    account = (account or "").strip()
    if not account:
        raise HTTPException(status_code=422, detail="account is required")
    return {
        "account_id": account,
        "last_deal_timestamp": int(database.get_last_deal_timestamp(account) or 0),
        "safety_barrier": _SAFETY,
    }


@router.post("/mt5")
def mt5_ingest_endpoint(payload: MT5Payload, request: Request) -> Dict[str, Any]:
    """Persist one MT5 snapshot for the calling user."""
    if len(payload.deals) > mt5_ingest.MAX_DEALS_PER_PUSH:
        raise HTTPException(
            status_code=413,
            detail=f"too many deals in one push (max {mt5_ingest.MAX_DEALS_PER_PUSH})",
        )
    try:
        summary = mt5_ingest.ingest_mt5_payload(
            payload.account_id,
            balance=payload.balance.model_dump() if payload.balance else None,
            positions=(
                [p.model_dump() for p in payload.positions]
                if payload.positions is not None
                else None
            ),
            deals=[d.model_dump() for d in payload.deals],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**summary, "safety_barrier": _SAFETY}
