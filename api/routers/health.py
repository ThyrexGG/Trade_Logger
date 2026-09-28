# -*- coding: utf-8 -*-
"""
FastAPI Health Router — Stage 2 Lightweight Health & Safety Configuration Status
"""
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import database
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


@router.get("/health/db")
async def get_health_db():
    """Unlike /health, this ACTUALLY touches the database -- a trivial ``SELECT 1``.
    /health deliberately stays green even when the DB is unreachable (e.g. Neon's
    compute-hour quota exceeded), which is correct for "is the process alive" but
    means nothing external can tell the difference between "server down" and
    "server up, database dead" from /health alone. This is what the desktop
    app's auto-fallback-to-local-copy feature polls instead."""
    try:
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:
        return JSONResponse({"status": "DB_UNREACHABLE", "detail": str(exc)[:300]}, status_code=503)
    return {"status": "OK", "timestamp": datetime.now(timezone.utc).isoformat()}
