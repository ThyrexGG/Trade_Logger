# -*- coding: utf-8 -*-
"""
TradeLogger FastAPI Primary Application Entry Point (Stage 2 Read-Only Vertical Slice)
Provides high-speed, typed, read-only adapter endpoints directly invoking
authoritative Python calculation engines without logic duplication.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database
from api.routers import (
    health,
    watchlist,
    market,
    preferences,
    intelligence,
    risk,
    positions,
    evidence,
    research,
    operations,
    alerts,
    analytics,
    command_center,
    ai,
    macro
)

def _warm_up() -> None:
    """Best-effort startup warm-up.

    The first request to several pages otherwise pays a one-off ~1 s cost:
    lazy engine imports inside the route plus the initial (uncached) DB read.
    Priming them here moves that cost to process start, before uvicorn accepts
    traffic, so the first real user navigation is as fast as a warm one. Every
    step is guarded — a slow or unreachable dependency must never stop boot.
    """
    try:
        conn = database.get_connection()   # builds + primes the pg pool
        conn.close()
    except Exception:
        pass

    # A bare TestClient (no `with`) does not re-enter this lifespan; it just
    # lets us exercise the read routes to trigger their lazy imports + cache fill.
    from fastapi.testclient import TestClient

    client = TestClient(app)
    for path in (
        "/api/watchlist",
        "/api/positions",
        "/api/analytics/performance",
        "/api/operations/audit",
        "/api/operations/system",
        "/api/command-center/overview",
        "/api/intelligence/asset/XAUUSD",
    ):
        try:
            client.get(path)
        except Exception:
            pass

    # If a real macro provider is configured (Phase 65), prime its data now —
    # budget-bounded and fully guarded — so the first macro request is fast and
    # a broken provider degrades before it ever reaches a user.
    import os as _os

    if (_os.getenv("MACRO_DATA_PROVIDER") or "").strip().lower() == "fred":
        try:
            from api.providers.fred_provider import FredMacroProvider
            FredMacroProvider().hydrate_registry()
        except Exception:
            pass

    # Phase 66 — prime the CFTC COT provider on the same terms if selected.
    if (_os.getenv("MACRO_COT_PROVIDER") or "").strip().lower() == "cftc":
        try:
            from api.providers.cftc_provider import CftcCotProvider
            CftcCotProvider().hydrate_registry()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import os

    if os.getenv("TL_SKIP_WARMUP", "").strip() not in ("1", "true", "True"):
        try:
            _warm_up()
        except Exception:
            pass
    yield
    # Return every pooled socket cleanly on shutdown.
    try:
        database.close_all_pools()
    except Exception:
        pass


# Initialize FastAPI App
app = FastAPI(
    title="TradeLogger Fast Terminal API",
    description="High-speed read-only adapter layer for TradeLogger quantitative trading & research terminal",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for React SPA (Vite dev port 5173, preview 4173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Register Stage 2 & Stage 3 Routers
app.include_router(health.router)
app.include_router(watchlist.router)
app.include_router(market.router)
app.include_router(preferences.router)
app.include_router(intelligence.router)
app.include_router(risk.router)
app.include_router(positions.router)
app.include_router(evidence.router)
app.include_router(research.router)
app.include_router(operations.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(command_center.router)
app.include_router(ai.router)
app.include_router(macro.router)


@app.get("/")
async def root():
    return {
        "app": "TradeLogger Fast Terminal API",
        "version": "2.0.0",
        "status": "ONLINE",
        "docs": "/docs"
    }
