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
from api import identity

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
    mode: str  # "passphrase" | "supabase"
    timestamp: str


class MeResponse(BaseModel):
    mode: str
    authenticated: bool
    user: dict | None = None
    error: str | None = None
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


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user.get("display_name"),
        "role": user.get("role", "member"),
    }


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request) -> AuthStatusResponse:
    mode = identity.auth_mode()
    if mode == "supabase":
        required = True
        authed = identity.resolve_user(_token_from(request)) is not None
    else:
        required = auth.auth_enabled()
        authed = (not required) or auth.validate_token(_token_from(request))
    return AuthStatusResponse(
        auth_required=required, authenticated=authed, mode=mode, timestamp=_now()
    )


@router.get("/me", response_model=MeResponse)
async def auth_me(request: Request) -> MeResponse:
    """Current user profile (supabase mode). Surfaces *why* a valid Supabase
    session is still locked out — an un-invited email needs the owner to add
    it to TL_SIGNUP_ALLOWLIST, which is a different fix from "log in again"."""
    mode = identity.auth_mode()
    if mode != "supabase":
        return MeResponse(mode=mode, authenticated=True, user=None, timestamp=_now())

    token = _token_from(request)
    if not token:
        return MeResponse(mode=mode, authenticated=False, timestamp=_now())
    try:
        user = identity.resolve_user_strict(token)
        return MeResponse(mode=mode, authenticated=True, user=_public_user(user), timestamp=_now())
    except identity.InvalidToken:
        return MeResponse(mode=mode, authenticated=False, error="Session expired. Sign in again.", timestamp=_now())
    except identity.NotAllowed as exc:
        return MeResponse(mode=mode, authenticated=False, error=f"Access not granted: {exc}", timestamp=_now())


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
    if identity.auth_mode() == "supabase":
        response.status_code = 400
        return LoginResponse(
            ok=False,
            error="This server uses Supabase sign-in — log in through the app, not this endpoint.",
            timestamp=_now(),
        )
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
