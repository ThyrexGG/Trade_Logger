# -*- coding: utf-8 -*-
"""
TradeLogger FastAPI Primary Application Entry Point (Stage 2 Read-Only Vertical Slice)
Provides high-speed, typed, read-only adapter endpoints directly invoking
authoritative Python calculation engines without logic duplication.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import database
import tenant as _tenant
from api import auth as _auth
from api import identity as _identity
from api.routers import (
    health,
    auth as auth_router,
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
    macro,
    strategy_research,
    trade_setup,
    accounts,
    system_control,
    connections,
    admin,
    ingest,
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

    # Stage 18G — prime the economic-calendar provider (ForexFactory / FMP) so
    # the first macro request has a calendar and a fresh last-good snapshot.
    if (_os.getenv("MACRO_CALENDAR_PROVIDER") or "").strip().lower() != "none":
        try:
            from api.providers.calendar_provider import get_calendar_provider
            get_calendar_provider().hydrate()
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
    try:
        from api import sync_service
        sync_service.start_if_enabled()
    except Exception:
        pass

    # Keep the AI-assistant context snapshot warm. Assembling it fans out to the
    # candle / evidence / macro engines and costs ~20-40s cold; refreshing it in
    # the background every ~30s means a chat message never waits on that.
    ai_ctx_task = None
    if os.getenv("TL_SKIP_WARMUP", "").strip() not in ("1", "true", "True"):
        import asyncio

        async def _keep_ai_context_warm() -> None:
            from api.ai_context import build_context
            from api.gemini_client import is_configured

            while True:
                try:
                    if is_configured():
                        await asyncio.to_thread(build_context, True)
                except Exception:
                    pass
                await asyncio.sleep(300)

        try:
            ai_ctx_task = asyncio.create_task(_keep_ai_context_warm())
        except Exception:
            ai_ctx_task = None

    yield

    if ai_ctx_task is not None:
        ai_ctx_task.cancel()
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

# --- CORS ---------------------------------------------------------------
# In production set TL_ALLOWED_ORIGINS to the frontend origin(s), comma-separated
# (e.g. "https://tradelogger.pages.dev"). With explicit origins we can send
# credentials (the session cookie). With no list set we fall back to the open
# dev config, which the browser forbids from carrying credentials.
_cors_origins = [o.strip() for o in os.getenv("TL_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=bool(_cors_origins),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- auth gate ---------------------------------------------------------
# Every /api/* route requires a valid session when auth is configured. Health,
# the auth routes themselves, and the OpenAPI docs are exempt.
#
#  * passphrase mode (default, W3): a session cookie / bearer token minted by
#    /api/auth/login. With no passphrase configured, auth is disabled and
#    local dev + the test suite are unaffected.
#  * supabase mode (W8, TL_AUTH_MODE=supabase): a Supabase access token in the
#    Authorization header, whose email must be invited (TL_SIGNUP_ALLOWLIST).
#    The resolved user is stashed on request.state for the per-user data layer.
_AUTH_EXEMPT = {
    "/", "/api/health",
    "/api/auth/login", "/api/auth/logout", "/api/auth/status", "/api/auth/me",
    "/api/auth/signup",
    "/docs", "/redoc", "/openapi.json", "/favicon.ico",
}


def _bearer(request: Request) -> str:
    h = request.headers.get("authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else ""


@app.middleware("http")
async def _auth_gate(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    exempt = (
        path in _AUTH_EXEMPT
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or not path.startswith("/api/")
    )

    if _identity.auth_mode() == "multiuser":
        tok = _bearer(request) or request.cookies.get(_auth.cookie_name(), "")
        user = _identity.resolve_session_user(tok)
        if user is not None:
            request.state.user = user
            request.state.user_id = user["id"]
            bound = _tenant.bind(user["id"])
            try:
                return await call_next(request)
            finally:
                _tenant.release(bound)
        if exempt:
            return await call_next(request)
        return JSONResponse({"detail": "Authentication required."}, status_code=401)

    if _identity.auth_mode() == "supabase":
        if not _identity.supabase_enabled():
            if exempt:
                return await call_next(request)
            return JSONResponse({"detail": "Auth is not configured on this server."}, status_code=503)
        user = _identity.resolve_user(_bearer(request))
        if user is not None:
            request.state.user = user
            request.state.user_id = user["id"]
            token = _tenant.bind(user["id"])
            try:
                return await call_next(request)
            finally:
                _tenant.release(token)
        if exempt:
            return await call_next(request)
        return JSONResponse({"detail": "Authentication required."}, status_code=401)

    # passphrase mode
    if not _auth.auth_enabled():
        return await call_next(request)
    if exempt:
        return await call_next(request)
    bearer = _bearer(request)
    token = bearer or request.cookies.get(_auth.cookie_name(), "")
    if _auth.validate_token(token):
        return await call_next(request)
    return JSONResponse({"detail": "Authentication required."}, status_code=401)

# Register Stage 2 & Stage 3 Routers
app.include_router(health.router)
app.include_router(auth_router.router)
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
app.include_router(strategy_research.router)
app.include_router(trade_setup.router)
app.include_router(accounts.router)
app.include_router(system_control.router)
app.include_router(connections.router)
app.include_router(admin.router)
app.include_router(ingest.router)


@app.get("/")
async def root():
    return {
        "app": "TradeLogger Fast Terminal API",
        "version": "2.0.0",
        "status": "ONLINE",
        "docs": "/docs"
    }
