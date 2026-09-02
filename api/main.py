# -*- coding: utf-8 -*-
"""
TradeLogger FastAPI Primary Application Entry Point (Stage 2 Read-Only Vertical Slice)
Provides high-speed, typed, read-only adapter endpoints directly invoking
authoritative Python calculation engines without logic duplication.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    health,
    watchlist,
    market,
    preferences,
    intelligence,
    risk,
    positions,
    evidence
)

# Initialize FastAPI App
app = FastAPI(
    title="TradeLogger Fast Terminal API",
    description="High-speed read-only adapter layer for TradeLogger quantitative trading & research terminal",
    version="2.0.0"
)

# Enable CORS for React SPA (Vite dev port 5173, preview 4173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
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


@app.get("/")
async def root():
    return {
        "app": "TradeLogger Fast Terminal API",
        "version": "2.0.0",
        "status": "ONLINE",
        "docs": "/docs"
    }
