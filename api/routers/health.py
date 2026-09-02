# -*- coding: utf-8 -*-
"""
FastAPI Health Router — Stage 2 Lightweight Health & Safety Configuration Status
"""
from datetime import datetime, timezone
from fastapi import APIRouter
from api.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Lightweight health endpoint returning basic process status and
    authoritative fail-closed safety gate configuration.
    Does not trigger broker connection or expensive engine initialization.
    """
    return HealthResponse(
        status="HEALTHY",
        app_name="TradeLogger Fast Terminal API",
        version="2.0.0",
        live_broker_transmission="BLOCKED",
        automation_enabled=False,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
