# -*- coding: utf-8 -*-
"""
Multi-user identity (platform plan W8.1).

Supabase Auth is the identity provider. The frontend signs a user in with
``@supabase/supabase-js`` and sends the access token as an
``Authorization: Bearer`` header. This module verifies that token against the
project's JWT secret (HS256, **stdlib only** — no new dependency, same spirit as
``api/auth.py`` hand-rolling scrypt) and provisions a local ``users`` row the
first time an allow-listed email is seen.

Two auth modes, selected by ``TL_AUTH_MODE``:

* ``passphrase`` (default) — the single-user W3 flow in ``api/auth.py`` is
  unchanged. ``current_user_id()`` returns the fixed local id so the
  per-user data layer (W8.4) has something to scope to.
* ``supabase`` — every ``/api/*`` route (bar the exempt set) needs a valid
  Supabase JWT whose email is on ``TL_SIGNUP_ALLOWLIST`` (or is
  ``TL_OWNER_EMAIL``). Anyone else gets 403 even with a valid Supabase
  session — sign-up is invite-only for a handful of friends.

Still no order path. Identity only decides *whose* journal rows a request may
read and write. The frozen research/execution layer and macro data stay global
and read-only for everyone.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import database

# The user id every row is stamped with when the server runs in single-user
# ``passphrase`` mode (local dev, the test suite, the current live deploy).
# W8.4 backfills existing rows to this id, so switching a box to ``supabase``
# mode later means re-owning those rows to a real account, not losing them.
LOCAL_USER_ID = "local"

_users_ready = False
_users_lock = threading.Lock()

# The JWT is re-verified (cheap, stdlib HMAC) on every request, but the
# provisioning round-trip to the DB — the "upsert + touch last_seen" — is
# throttled per user so a polling client does not write a row every second.
# A disabled account therefore takes up to _PROVISION_TTL_SEC to lock out.
_PROVISION_TTL_SEC = 60
_provision_cache: Dict[str, tuple] = {}   # user_id -> (user_dict, monotonic_ts)
_provision_cache_lock = threading.Lock()

# A valid Supabase token whose email is not invited is refused every request.
# Cache that "no" briefly so a client retrying in a loop doesn't re-hit the
# allowlist + DB each time (cheap DoS guard for the invite-only surface).
_DENY_TTL_SEC = 30
_deny_cache: Dict[str, tuple] = {}        # user_id -> (reason, monotonic_ts)


class InvalidToken(Exception):
    """The bearer token is missing, malformed, expired or wrongly signed."""


class NotAllowed(Exception):
    """A valid Supabase user whose email is not invited (or is disabled)."""


# --- env ------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def auth_mode() -> str:
    v = _env("TL_AUTH_MODE", "passphrase").lower()
    return "supabase" if v == "supabase" else "passphrase"


def _jwt_secret() -> str:
    return _env("SUPABASE_JWT_SECRET")


def supabase_url() -> str:
    """The project URL, e.g. ``https://abc.supabase.co`` (no trailing slash).

    Used to discover the JWKS endpoint for the asymmetric (ES256/RS256)
    signing keys and to pin the token issuer. Optional — if unset, the
    issuer claim on a verified token is used for key discovery instead.
    """
    return _env("SUPABASE_URL").rstrip("/")


def supabase_enabled() -> bool:
    # Either signing scheme is enough to run: the legacy shared secret
    # (HS256) or the project URL for the asymmetric keys (ES256/RS256).
    return auth_mode() == "supabase" and bool(_jwt_secret() or supabase_url())


def owner_email() -> str:
    return _env("TL_OWNER_EMAIL").lower()


def signup_allowlist() -> set[str]:
    """Lower-cased invited emails. ``TL_OWNER_EMAIL`` is always included."""
    raw = _env("TL_SIGNUP_ALLOWLIST")
    emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
    owner = owner_email()
    if owner:
        emails.add(owner)
    return emails


# --- JWT verification --------------------------------------------------
#
# Supabase issues access tokens under one of two signing schemes:
#   * HS256 — the legacy project "JWT secret" (a shared symmetric key). Verified
#     with stdlib HMAC, no network call.
#   * ES256 / RS256 — the newer asymmetric signing keys. The public half is
#     published at ``<project>/auth/v1/.well-known/jwks.json``; we fetch and
#     cache it and verify with ``cryptography`` (already a dependency).
# Both are accepted so a project on either scheme just works.

_JWKS_TTL_SEC = 600
_jwks_cache: Dict[str, tuple] = {}       # jwks_url -> ({kid: jwk}, monotonic_ts)
_jwks_lock = threading.Lock()
_ASYM_ALGS = {"ES256", "RS256"}


def _b64url_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def _b64url_uint(segment: str) -> int:
    return int.from_bytes(_b64url_decode(segment), "big")


def _jwks_url(issuer: str) -> str:
    base = supabase_url() or (issuer or "").rstrip("/")
    if not base:
        raise InvalidToken("no issuer / SUPABASE_URL for signing-key discovery")
    if base.endswith("/auth/v1"):
        return f"{base}/.well-known/jwks.json"
    return f"{base}/auth/v1/.well-known/jwks.json"


def _fetch_jwks(url: str, *, force: bool = False) -> Dict[str, dict]:
    now = time.monotonic()
    if not force:
        with _jwks_lock:
            hit = _jwks_cache.get(url)
            if hit and now - hit[1] < _JWKS_TTL_SEC:
                return hit[0]
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - https project URL
            doc = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - network/parse
        with _jwks_lock:
            hit = _jwks_cache.get(url)
        if hit:
            return hit[0]      # serve stale rather than lock everyone out
        raise InvalidToken(f"could not fetch signing keys: {exc}") from exc
    keys = {k["kid"]: k for k in doc.get("keys", []) if k.get("kid")}
    with _jwks_lock:
        _jwks_cache[url] = (keys, now)
    return keys


def _public_key_from_jwk(jwk: Dict[str, Any]):
    from cryptography.hazmat.primitives.asymmetric import ec, rsa

    kty = jwk.get("kty")
    if kty == "EC":
        if jwk.get("crv") != "P-256":
            raise InvalidToken(f"unsupported EC curve {jwk.get('crv')!r}")
        return ec.EllipticCurvePublicNumbers(
            _b64url_uint(jwk["x"]), _b64url_uint(jwk["y"]), ec.SECP256R1()
        ).public_key()
    if kty == "RSA":
        return rsa.RSAPublicNumbers(
            _b64url_uint(jwk["e"]), _b64url_uint(jwk["n"])
        ).public_key()
    raise InvalidToken(f"unsupported key type {kty!r}")


def _verify_asymmetric(
    signing_input: bytes, signature: bytes, alg: str, kid: str, issuer: str
) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding
    from cryptography.hazmat.primitives.asymmetric import utils as asym_utils

    if not kid:
        raise InvalidToken("token header has no kid")
    pinned = supabase_url()
    if pinned and issuer and not issuer.rstrip("/").startswith(pinned):
        raise InvalidToken("token issuer does not match SUPABASE_URL")

    url = _jwks_url(issuer)
    jwk = _fetch_jwks(url).get(kid) or _fetch_jwks(url, force=True).get(kid)
    if jwk is None:
        raise InvalidToken(f"no signing key for kid {kid!r}")

    pub = _public_key_from_jwk(jwk)
    try:
        if alg == "ES256":
            if len(signature) != 64:
                raise InvalidToken("malformed ES256 signature")
            der = asym_utils.encode_dss_signature(
                int.from_bytes(signature[:32], "big"),
                int.from_bytes(signature[32:], "big"),
            )
            pub.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
        elif alg == "RS256":
            pub.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        else:  # pragma: no cover - guarded by caller
            raise InvalidToken(f"unsupported alg {alg!r}")
    except InvalidSignature as exc:
        raise InvalidToken("bad signature") from exc
    except (ValueError, TypeError) as exc:
        raise InvalidToken(f"signature check failed: {exc}") from exc


def decode_token(token: str, *, leeway: int = 30) -> Dict[str, Any]:
    """Verify a Supabase access token (HS256 or ES256/RS256) and return its
    claims. Raises :class:`InvalidToken` on any problem."""
    if not token or token.count(".") != 2:
        raise InvalidToken("not a JWT")

    header_b64, payload_b64, sig_b64 = token.split(".")
    try:
        header = json.loads(_b64url_decode(header_b64))
        claims = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(sig_b64)
    except Exception as exc:  # noqa: BLE001
        raise InvalidToken(f"malformed JWT: {exc}") from exc

    alg = header.get("alg")
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    if alg == "HS256":
        secret = _jwt_secret()
        if not secret:
            raise InvalidToken("SUPABASE_JWT_SECRET is not configured")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, signature):
            raise InvalidToken("bad signature")
    elif alg in _ASYM_ALGS:
        _verify_asymmetric(signing_input, signature, alg, header.get("kid", ""),
                           str(claims.get("iss") or ""))
    else:
        raise InvalidToken(f"unsupported alg {alg!r}")

    now = time.time()
    exp = claims.get("exp")
    if exp is not None and float(exp) < now - leeway:
        raise InvalidToken("expired")
    nbf = claims.get("nbf")
    if nbf is not None and float(nbf) > now + leeway:
        raise InvalidToken("not yet valid")

    aud = claims.get("aud")
    auds = aud if isinstance(aud, list) else [aud] if aud else []
    if auds and "authenticated" not in auds:
        raise InvalidToken(f"unexpected audience {aud!r}")

    if not claims.get("sub"):
        raise InvalidToken("no subject")
    return claims


# --- users table -------------------------------------------------------

def _ph(conn) -> str:
    return "%s" if database.is_postgres() else "?"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_users_table() -> None:
    global _users_ready
    if _users_ready:
        return
    with _users_lock:
        if _users_ready:
            return
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    role TEXT NOT NULL DEFAULT 'member',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
            _users_ready = True
        finally:
            conn.close()


def _row_to_user(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "email": row[1],
        "display_name": row[2],
        "role": row[3],
        "status": row[4],
        "created_at": row[5],
        "last_seen_at": row[6],
    }


_USER_COLS = "id, email, display_name, role, status, created_at, last_seen_at"


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {_USER_COLS} FROM users WHERE id = {_ph(conn)}", (user_id,))
        row = cur.fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()


def list_users() -> List[Dict[str, Any]]:
    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {_USER_COLS} FROM users ORDER BY created_at")
        return [_row_to_user(r) for r in cur.fetchall()]
    finally:
        conn.close()


def set_user_status(user_id: str, status: str) -> None:
    if status not in ("active", "disabled"):
        raise ValueError("status must be 'active' or 'disabled'")
    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"UPDATE users SET status = {ph} WHERE id = {ph}", (status, user_id))
        conn.commit()
    finally:
        conn.close()
    _forget(user_id)


def provision_user(claims: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert the local ``users`` row for a verified Supabase identity.

    Raises :class:`NotAllowed` if the email is not invited or the account has
    been disabled.
    """
    uid = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().lower()
    if not uid or not email:
        raise NotAllowed("token has no email")

    allow = signup_allowlist()
    if not allow:
        # Fail closed: with no allowlist and no owner configured nobody is in.
        raise NotAllowed("sign-up is not open on this server")
    if email not in allow:
        raise NotAllowed(f"{email} is not invited")

    meta = claims.get("user_metadata") or {}
    display = str(meta.get("full_name") or meta.get("name") or "").strip() or None
    role = "owner" if email == owner_email() else "member"
    now = _now_iso()

    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"SELECT {_USER_COLS} FROM users WHERE id = {ph}", (uid,))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                f"INSERT INTO users (id, email, display_name, role, status, created_at, last_seen_at) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, 'active', {ph}, {ph})",
                (uid, email, display, role, now, now),
            )
            conn.commit()
            return {
                "id": uid, "email": email, "display_name": display,
                "role": role, "status": "active", "created_at": now, "last_seen_at": now,
            }
        user = _row_to_user(row)
        if user["status"] == "disabled":
            raise NotAllowed("account disabled")
        # Keep email / display name fresh; never downgrade an existing role.
        cur.execute(
            f"UPDATE users SET email = {ph}, display_name = COALESCE({ph}, display_name), "
            f"last_seen_at = {ph} WHERE id = {ph}",
            (email, display, now, uid),
        )
        conn.commit()
        user["email"] = email
        user["last_seen_at"] = now
        if display:
            user["display_name"] = display
        return user
    finally:
        conn.close()


# --- request-time resolution -----------------------------------------

def resolve_user(token: str) -> Optional[Dict[str, Any]]:
    """Verified + provisioned user for a bearer token, or ``None``.

    ``None`` covers both "no / bad token" and "valid token but not invited" —
    the caller turns that into 401. Use :func:`resolve_user_strict` when the
    distinction matters (the login/status endpoints want to say *why*).
    """
    try:
        return resolve_user_strict(token)
    except (InvalidToken, NotAllowed):
        return None


def resolve_user_strict(token: str) -> Dict[str, Any]:
    claims = decode_token(token)
    uid = str(claims.get("sub") or "")
    now = time.monotonic()
    with _provision_cache_lock:
        hit = _provision_cache.get(uid)
        if hit and now - hit[1] < _PROVISION_TTL_SEC:
            return hit[0]
        deny = _deny_cache.get(uid)
        if deny and now - deny[1] < _DENY_TTL_SEC:
            raise NotAllowed(deny[0])
    try:
        user = provision_user(claims)
    except NotAllowed as exc:
        with _provision_cache_lock:
            _deny_cache[uid] = (str(exc), now)
        raise
    with _provision_cache_lock:
        _provision_cache[uid] = (user, now)
        _deny_cache.pop(uid, None)
    return user


def _forget(user_id: str) -> None:
    with _provision_cache_lock:
        _provision_cache.pop(user_id, None)
        _deny_cache.pop(user_id, None)


def current_user_id(request) -> str:
    """The id every per-user row for this request is scoped to.

    ``supabase`` mode: the authenticated user's id (the middleware has already
    put it on ``request.state``). ``passphrase`` / auth-disabled mode: the
    fixed :data:`LOCAL_USER_ID`.
    """
    uid = getattr(getattr(request, "state", None), "user_id", None)
    return uid or LOCAL_USER_ID
