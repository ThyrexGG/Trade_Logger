# -*- coding: utf-8 -*-
"""
FastAPI auth router.

Three modes, selected by ``TL_AUTH_MODE`` (see ``api/identity.auth_mode``):

* ``passphrase`` (W3, default) — one shared passphrase -> httpOnly session cookie.
* ``multiuser`` (W10) — per-account email + password, invite-only. Sign-up and
  sign-in both mint the same kind of session cookie/token; every account's
  rows are tenant-scoped downstream.
* ``supabase`` (W8, legacy) — an external Supabase JWT in the Authorization
  header. Kept working but no longer the recommended path.

Routes:
  ``POST /api/auth/signup``  — multiuser: create an invited account, sign in
  ``POST /api/auth/login``   — passphrase: passphrase; multiuser: email+password
  ``POST /api/auth/logout``  — revoke the current session
  ``GET  /api/auth/status``  — { auth_required, authenticated, mode }
  ``GET  /api/auth/me``      — current account (multiuser / supabase)

The blanket gate on every other ``/api/*`` route lives in ``api/main.py``.
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
    email: str | None = Field(default=None, max_length=254)


class SignupRequest(BaseModel):
    model_config = {"extra": "forbid"}
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=512)
    display_name: str | None = Field(default=None, max_length=120)


class LoginResponse(BaseModel):
    ok: bool
    error: str | None = None
    expires_at: str | None = None
    token: str | None = None          # for non-browser clients (the MT5 agent)
    user: dict | None = None
    timestamp: str


class AuthStatusResponse(BaseModel):
    auth_required: bool
    authenticated: bool
    mode: str  # "passphrase" | "multiuser" | "supabase"
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


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth.cookie_name(),
        value=token,
        max_age=auth.session_ttl_days() * 86400,
        httponly=True,
        samesite=auth.cookie_samesite(),
        secure=auth.cookie_secure(),
        path="/",
    )


# --- status / me -----------------------------------------------------

@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request) -> AuthStatusResponse:
    mode = identity.auth_mode()
    if mode == "multiuser":
        authed = identity.resolve_session_user(_token_from(request)) is not None
        return AuthStatusResponse(auth_required=True, authenticated=authed, mode=mode, timestamp=_now())
    if mode == "supabase":
        authed = identity.resolve_user(_token_from(request)) is not None
        return AuthStatusResponse(auth_required=True, authenticated=authed, mode=mode, timestamp=_now())
    required = auth.auth_enabled()
    authed = (not required) or bool(auth.validate_token(_token_from(request)))
    return AuthStatusResponse(auth_required=required, authenticated=authed, mode=mode, timestamp=_now())


@router.get("/me", response_model=MeResponse)
async def auth_me(request: Request) -> MeResponse:
    """Current account. In multiuser/supabase mode this also surfaces *why* a
    session is locked out (not invited vs. expired) so the UI can say the right
    thing."""
    mode = identity.auth_mode()
    if mode == "passphrase":
        return MeResponse(mode=mode, authenticated=True, user=None, timestamp=_now())

    token = _token_from(request)
    if not token:
        return MeResponse(mode=mode, authenticated=False, timestamp=_now())

    if mode == "multiuser":
        user = identity.resolve_session_user(token)
        if user is None:
            return MeResponse(mode=mode, authenticated=False,
                              error="Your session has ended. Sign in again.", timestamp=_now())
        return MeResponse(mode=mode, authenticated=True, user=_public_user(user), timestamp=_now())

    # supabase
    try:
        user = identity.resolve_user_strict(token)
        return MeResponse(mode=mode, authenticated=True, user=_public_user(user), timestamp=_now())
    except identity.InvalidToken:
        return MeResponse(mode=mode, authenticated=False, error="Session expired. Sign in again.", timestamp=_now())
    except identity.NotAllowed as exc:
        return MeResponse(mode=mode, authenticated=False, error=f"Access not granted: {exc}", timestamp=_now())


# --- sign up (multiuser only) --------------------------------------

@router.post("/signup", response_model=LoginResponse)
async def signup(body: SignupRequest, request: Request, response: Response) -> LoginResponse:
    if identity.auth_mode() != "multiuser":
        response.status_code = 404
        return LoginResponse(ok=False, error="Sign-up is not available on this server.", timestamp=_now())

    ip = _client_ip(request)
    wait = auth.rate_limited_for(ip)
    if wait is not None:
        response.status_code = 429
        return LoginResponse(ok=False, error=f"Too many attempts. Try again in {wait // 60 + 1} min.", timestamp=_now())

    try:
        user = identity.create_account(body.email, body.password, body.display_name or "")
    except identity.NotAllowed as exc:
        auth.record_login_failure(ip)
        response.status_code = 403
        return LoginResponse(ok=False, error=str(exc), timestamp=_now())
    except identity.EmailTaken:
        response.status_code = 409
        return LoginResponse(ok=False, error="An account with that email already exists - sign in instead.", timestamp=_now())
    except ValueError as exc:
        response.status_code = 422
        return LoginResponse(ok=False, error=str(exc), timestamp=_now())

    auth.record_login_success(ip)
    token, expires_at = auth.create_session(label=f"signup {ip}", user_id=user["id"])
    _set_session_cookie(response, token)
    return LoginResponse(ok=True, expires_at=expires_at, token=token,
                         user=_public_user(user), timestamp=_now())


# --- sign in --------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
    mode = identity.auth_mode()
    if mode == "supabase":
        response.status_code = 400
        return LoginResponse(ok=False, error="This server uses Supabase sign-in — log in through the app.", timestamp=_now())

    ip = _client_ip(request)
    wait = auth.rate_limited_for(ip)
    if wait is not None:
        response.status_code = 429
        return LoginResponse(ok=False, error=f"Too many attempts. Try again in {wait // 60 + 1} min.", timestamp=_now())

    if mode == "multiuser":
        if not body.email:
            response.status_code = 422
            return LoginResponse(ok=False, error="Email is required.", timestamp=_now())
        try:
            user = identity.verify_credentials(body.email, body.password)
        except identity.BadCredentials:
            auth.record_login_failure(ip)
            response.status_code = 401
            return LoginResponse(ok=False, error="Wrong email or password.", timestamp=_now())
        except identity.NotAllowed as exc:
            auth.record_login_failure(ip)
            response.status_code = 403
            return LoginResponse(ok=False, error=str(exc), timestamp=_now())
        auth.record_login_success(ip)
        token, expires_at = auth.create_session(label=f"login {ip}", user_id=user["id"])
        _set_session_cookie(response, token)
        return LoginResponse(ok=True, expires_at=expires_at, token=token,
                             user=_public_user(user), timestamp=_now())

    # passphrase
    if not auth.auth_enabled():
        return LoginResponse(ok=True, expires_at=None, timestamp=_now())
    if not auth.verify_password(body.password):
        auth.record_login_failure(ip)
        response.status_code = 401
        return LoginResponse(ok=False, error="Incorrect passphrase.", timestamp=_now())
    auth.record_login_success(ip)
    token, expires_at = auth.create_session(label=f"login {ip}")
    _set_session_cookie(response, token)
    return LoginResponse(ok=True, expires_at=expires_at, token=token, timestamp=_now())


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
