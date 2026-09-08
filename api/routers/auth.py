# -*- coding: utf-8 -*-
"""
FastAPI auth router (platform plan W3) — single-user session login.

`POST /api/auth/login`  — passphrase -> httpOnly session cookie
`POST /api/auth/logout` — revoke the current session
`GET  /api/auth/status` — { auth_required, authenticated } (safe unauthenticated)

The blanket `Authorization` gate on every other `/api/*` route lives in
`api/main.py` as HTTP middleware. This router is exempt from it.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from api import auth

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    model_config = {"extra": "forbid"}
    password: str = Field(min_length=1, max_length=512)


class LoginResponse(BaseModel):
    ok: bool
    error: str | None = None
    expires_at: str | None = None
    timestamp: str


class AuthStatusResponse(BaseModel):
    auth_required: bool
    authenticated: bool
    timestamp: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _token_from(request: Request) -> str:
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        return bearer[7:].strip()
    return request.cookies.get(auth.cookie_name(), "")


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request) -> AuthStatusResponse:
    required = auth.auth_enabled()
    authed = (not required) or auth.validate_token(_token_from(request))
    return AuthStatusResponse(auth_required=required, authenticated=authed, timestamp=_now())


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
    if not auth.auth_enabled():
        return LoginResponse(ok=True, expires_at=None, timestamp=_now())

    ip = _client_ip(request)
    wait = auth.rate_limited_for(ip)
    if wait is not None:
        response.status_code = 429
        return LoginResponse(
            ok=False,
            error=f"Too many attempts. Try again in {wait // 60 + 1} min.",
            timestamp=_now(),
        )

    if not auth.verify_password(body.password):
        auth.record_login_failure(ip)
        response.status_code = 401
        return LoginResponse(ok=False, error="Incorrect passphrase.", timestamp=_now())

    auth.record_login_success(ip)
    token, expires_at = auth.create_session(label=f"login {ip}")
    max_age = auth.session_ttl_days() * 86400
    response.set_cookie(
        key=auth.cookie_name(),
        value=token,
        max_age=max_age,
        httponly=True,
        samesite=auth.cookie_samesite(),
        secure=auth.cookie_secure(),
        path="/",
    )
    return LoginResponse(ok=True, expires_at=expires_at, timestamp=_now())


@router.post("/logout", response_model=LoginResponse)
async def logout(request: Request, response: Response) -> LoginResponse:
    token = _token_from(request)
    if token:
        auth.revoke_token(token)
    response.delete_cookie(
        auth.cookie_name(),
        path="/",
        samesite=auth.cookie_samesite(),
        secure=auth.cookie_secure(),
        httponly=True,
    )
    return LoginResponse(ok=True, timestamp=_now())
